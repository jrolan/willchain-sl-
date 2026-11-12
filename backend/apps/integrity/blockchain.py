import json
from pathlib import Path
from datetime import timedelta

from eth_account import Account
from requests.exceptions import RequestException
from web3 import HTTPProvider, Web3
from web3.exceptions import TransactionNotFound, Web3Exception
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .crypto import decrypt_secret, encrypt_secret
from .models import AnchorStatus, DocumentIntegrityRecord, WillIntegrityRecord


class BlockchainConfigurationError(Exception):
    pass


class BlockchainUnavailable(Exception):
    pass


ABI_PATH = Path(__file__).with_name('contract_abi.json')


def _client(record, *, signing=False):
    rpc_url = getattr(settings, 'INTEGRITY_RPC_URL', '')
    contract_address = record.contract_address or getattr(settings, 'INTEGRITY_CONTRACT_ADDRESS', '')
    if not rpc_url or not contract_address:
        raise BlockchainConfigurationError('Blockchain provider or contract is not configured.')
    if not Web3.is_address(contract_address):
        raise BlockchainConfigurationError('Blockchain contract address is invalid.')

    web3 = Web3(HTTPProvider(rpc_url, request_kwargs={'timeout': settings.INTEGRITY_RPC_TIMEOUT}))
    try:
        if not web3.is_connected():
            raise BlockchainUnavailable('Blockchain provider is unavailable.')
        if web3.eth.chain_id != record.chain_id:
            raise BlockchainConfigurationError('Configured chain ID does not match the integrity record.')
        abi = json.loads(ABI_PATH.read_text(encoding='utf-8'))
        contract = web3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
        account = None
        if signing:
            private_key = getattr(settings, 'INTEGRITY_SIGNER_PRIVATE_KEY', '')
            if not private_key:
                raise BlockchainConfigurationError('Blockchain signing is not configured.')
            try:
                account = Account.from_key(private_key)
            except ValueError as error:
                raise BlockchainConfigurationError('Blockchain signing configuration is invalid.') from error
        return web3, contract, account
    except (RequestException, OSError, Web3Exception) as error:
        raise BlockchainUnavailable('Blockchain provider is unavailable.') from error


def _record_bytes(record):
    return bytes.fromhex(record.record_reference)


def _check_anchor_event(record, contract, receipt):
    if receipt['status'] != 1:
        return False

    if isinstance(record, WillIntegrityRecord):
        event_name = 'WillCommitmentRegistered'
    else:
        event_name = 'DocumentCommitmentRegistered'
    events = getattr(contract.events, event_name)().process_receipt(receipt)
    for event in events:
        args = event['args']
        if (
            bytes(args['recordId']) == _record_bytes(record)
            and bytes(args['commitment']) == bytes.fromhex(record.commitment)
            and (
                isinstance(record, WillIntegrityRecord)
                or bytes(args['willRecordId']) == _record_bytes(record.will_record)
            )
        ):
            return True
    return False


def verify_anchor(record):
    web3, contract, _ = _client(record)
    expected_commitment = bytes.fromhex(record.commitment)
    record_id = _record_bytes(record)

    try:
        if isinstance(record, WillIntegrityRecord):
            on_chain = contract.functions.getWillCommitment(record_id).call()[0]
            commitment_matches = contract.functions.verifyWillCommitment(record_id, expected_commitment).call()
        else:
            on_chain = contract.functions.getDocumentCommitment(record_id).call()[0]
            commitment_matches = contract.functions.verifyDocumentCommitment(record_id, expected_commitment).call()

        if bytes(on_chain) != expected_commitment or not commitment_matches:
            return False
        if not record.transaction_hash:
            return False
        receipt = web3.eth.get_transaction_receipt(record.transaction_hash)
        if receipt['status'] != 1 or receipt['blockNumber'] != record.block_number:
            return False
        if Web3.to_checksum_address(receipt['to']) != contract.address:
            return False
        required = settings.INTEGRITY_CONFIRMATIONS
        confirmations = max(0, web3.eth.block_number - receipt['blockNumber'] + 1)
        return confirmations >= required and _check_anchor_event(record, contract, receipt)
    except TransactionNotFound:
        return False
    except (RequestException, OSError, Web3Exception, ValueError) as error:
        raise BlockchainUnavailable('Blockchain provider is unavailable.') from error


def _save_status(record, **fields):
    for name, value in fields.items():
        setattr(record, name, value)
    record.save(update_fields=(*fields.keys(), 'updated_at'))


def _process_receipt(record, web3, contract, receipt):
    block_number = receipt['blockNumber']
    confirmations = max(0, web3.eth.block_number - block_number + 1)
    values = {
        'block_number': block_number,
        'confirmations': confirmations,
        'encrypted_raw_transaction': '',
    }
    if receipt['status'] != 1 or not _check_anchor_event(record, contract, receipt):
        _save_status(
            record,
            **values,
            anchor_status=AnchorStatus.FAILED,
            last_error_code='TRANSACTION_REVERTED',
        )
        return
    if confirmations < settings.INTEGRITY_CONFIRMATIONS:
        _save_status(
            record,
            **values,
            anchor_status=AnchorStatus.SUBMITTED,
            last_error_code='CONFIRMATIONS_PENDING',
        )
        return
    _save_status(
        record,
        **values,
        anchor_status=AnchorStatus.CONFIRMED,
        confirmed_at=timezone.now(),
        last_error_code='',
    )


def _build_and_submit(record, web3, contract, account):
    if (
        account.address.lower() != contract.functions.owner().call().lower()
        and not contract.functions.registrars(account.address).call()
    ):
        raise BlockchainConfigurationError('Configured signer is not an authorized registrar.')
    method = (
        contract.functions.registerWill(_record_bytes(record), bytes.fromhex(record.commitment))
        if isinstance(record, WillIntegrityRecord)
        else contract.functions.registerDocument(
            _record_bytes(record),
            _record_bytes(record.will_record),
            bytes.fromhex(record.commitment),
        )
    )
    nonce = web3.eth.get_transaction_count(account.address, 'pending')
    transaction_data = method.build_transaction({
        'from': account.address,
        'nonce': nonce,
        'chainId': record.chain_id,
        'gasPrice': web3.eth.gas_price,
    })
    transaction_data['gas'] = int(web3.eth.estimate_gas(transaction_data) * 1.2)
    signed = account.sign_transaction(transaction_data)
    raw_transaction = bytes(signed.raw_transaction)
    transaction_hash = Web3.to_hex(signed.hash)

    _save_status(
        record,
        anchor_status=AnchorStatus.SUBMITTED,
        contract_address=contract.address,
        transaction_hash=transaction_hash,
        encrypted_raw_transaction=encrypt_secret('signed-transaction', raw_transaction),
        submitted_at=timezone.now(),
        last_error_code='',
    )
    try:
        web3.eth.send_raw_transaction(raw_transaction)
    except (RequestException, OSError, Web3Exception, ValueError):
        _save_status(record, last_error_code='RPC_SUBMISSION_UNCONFIRMED')


def process_anchor(record):
    if record.anchor_status == AnchorStatus.CONFIRMED:
        try:
            if not verify_anchor(record):
                _save_status(
                    record,
                    anchor_status=AnchorStatus.FAILED,
                    last_error_code='CHAIN_REORGANIZATION_DETECTED',
                )
        except (BlockchainConfigurationError, BlockchainUnavailable, RequestException, OSError, Web3Exception):
            pass
        return record
    if (
        isinstance(record, DocumentIntegrityRecord)
        and record.will_record.anchor_status != AnchorStatus.CONFIRMED
    ):
        _save_status(record, last_error_code='WILL_ANCHOR_PENDING')
        return record

    try:
        web3, contract, account = _client(record, signing=record.anchor_status != AnchorStatus.SUBMITTED)
        if record.anchor_status == AnchorStatus.SUBMITTED and record.transaction_hash:
            try:
                receipt = web3.eth.get_transaction_receipt(record.transaction_hash)
            except TransactionNotFound:
                receipt = None
            if receipt is not None:
                _process_receipt(record, web3, contract, receipt)
                return record
            if record.encrypted_raw_transaction:
                raw_transaction = decrypt_secret('signed-transaction', record.encrypted_raw_transaction)
                try:
                    web3.eth.send_raw_transaction(raw_transaction)
                except (RequestException, OSError, Web3Exception):
                    _save_status(record, last_error_code='RPC_SUBMISSION_UNCONFIRMED')
            return record

        if isinstance(record, DocumentIntegrityRecord) and not record.commitment:
            _save_status(
                record,
                anchor_status=AnchorStatus.FAILED,
                last_error_code='DOCUMENT_CONTENT_UNVERIFIED',
            )
            return record

        claimed = type(record).objects.filter(
            pk=record.pk,
            anchor_status=AnchorStatus.QUEUED,
        ).update(
            anchor_status=AnchorStatus.SUBMITTING,
            attempts=record.attempts + 1,
            updated_at=timezone.now(),
        )
        if not claimed:
            record.refresh_from_db()
            return record
        record.anchor_status = AnchorStatus.SUBMITTING
        _build_and_submit(record, web3, contract, account)
    except BlockchainConfigurationError:
        fields = {'last_error_code': 'CHAIN_CONFIGURATION_MISSING'}
        if record.anchor_status == AnchorStatus.SUBMITTING:
            fields['anchor_status'] = AnchorStatus.QUEUED
        _save_status(record, **fields)
    except BlockchainUnavailable:
        fields = {'last_error_code': 'RPC_UNAVAILABLE'}
        if record.anchor_status == AnchorStatus.SUBMITTING:
            fields['anchor_status'] = AnchorStatus.QUEUED
        _save_status(record, **fields)
    except (RequestException, OSError, Web3Exception):
        if record.anchor_status == AnchorStatus.SUBMITTING:
            _save_status(
                record,
                anchor_status=AnchorStatus.QUEUED,
                last_error_code='RPC_UNAVAILABLE',
            )
        else:
            _save_status(record, last_error_code='RPC_UNAVAILABLE')
    except ValueError:
        _save_status(
            record,
            anchor_status=AnchorStatus.FAILED,
            encrypted_raw_transaction='',
            last_error_code='TRANSACTION_INPUT_INVALID',
        )
    except TypeError:
        _save_status(
            record,
            anchor_status=AnchorStatus.FAILED,
            encrypted_raw_transaction='',
            last_error_code='TRANSACTION_BUILD_FAILED',
        )

    record.refresh_from_db()
    if record.anchor_status == AnchorStatus.SUBMITTED:
        try:
            web3, contract, _ = _client(record)
            receipt = web3.eth.get_transaction_receipt(record.transaction_hash)
            _process_receipt(record, web3, contract, receipt)
        except TransactionNotFound:
            pass
        except BlockchainUnavailable:
            _save_status(record, last_error_code='RPC_UNAVAILABLE')
        except (RequestException, OSError, Web3Exception):
            _save_status(record, last_error_code='RPC_UNAVAILABLE')
        except ValueError:
            _save_status(
                record,
                anchor_status=AnchorStatus.FAILED,
                encrypted_raw_transaction='',
                last_error_code='REGISTRATION_EVENT_INVALID',
            )
    return record


def reset_stale_submissions():
    stale_before = timezone.now() - timedelta(minutes=5)
    for model in (WillIntegrityRecord, DocumentIntegrityRecord):
        model.objects.filter(
            anchor_status=AnchorStatus.SUBMITTING,
            updated_at__lt=stale_before,
        ).update(anchor_status=AnchorStatus.QUEUED, last_error_code='RETRY_AFTER_INTERRUPTION')
