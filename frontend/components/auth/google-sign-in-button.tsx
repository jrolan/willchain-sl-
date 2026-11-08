"use client";

import Script from "next/script";
import { useEffect, useRef } from "react";

const GOOGLE_CREDENTIAL_EVENT = "willchain:google-credential";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
            auto_select?: boolean;
          }) => void;
          renderButton: (element: HTMLElement, options: Record<string, string>) => void;
        };
      };
    };
    willChainGoogleClientId?: string;
  }
}

export function GoogleSignInButton({
  onCredential,
  onError,
}: {
  onCredential: (idToken: string) => void | Promise<void>;
  onError: (message: string) => void;
}) {
  const button = useRef<HTMLDivElement>(null);
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH2_CLIENT_ID;

  useEffect(() => {
    const handleCredential = (event: Event) => {
      const credential = (event as CustomEvent<{ credential?: string }>).detail?.credential;
      if (!credential) {
        onError("Google did not return a sign-in credential. Please try again.");
        return;
      }
      Promise.resolve(onCredential(credential)).catch((error: unknown) => {
        onError(error instanceof Error ? error.message : "Google sign in failed.");
      });
    };
    window.addEventListener(GOOGLE_CREDENTIAL_EVENT, handleCredential);
    return () => window.removeEventListener(GOOGLE_CREDENTIAL_EVENT, handleCredential);
  }, [onCredential, onError]);

  function initialize() {
    const target = button.current;
    if (!clientId || !target || !window.google) return;

    if (!window.willChainGoogleClientId) {
      window.google.accounts.id.initialize({
        client_id: clientId,
        auto_select: false,
        callback: ({ credential }) => {
          window.dispatchEvent(
            new CustomEvent(GOOGLE_CREDENTIAL_EVENT, { detail: { credential } }),
          );
        },
      });
      window.willChainGoogleClientId = clientId;
    }
    target.replaceChildren();
    window.google.accounts.id.renderButton(target, {
      type: "standard",
      theme: "outline",
      size: "large",
      text: "continue_with",
      shape: "rectangular",
      width: "320",
    });
  }

  if (!clientId) return null;

  return (
    <>
      <div className="my-6 flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-[#718078]">
        <span className="h-px flex-1 bg-[#dce4df]" />
        <span>Or continue with</span>
        <span className="h-px flex-1 bg-[#dce4df]" />
      </div>
      <div ref={button} className="flex min-h-10 justify-center" />
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={initialize} />
    </>
  );
}
