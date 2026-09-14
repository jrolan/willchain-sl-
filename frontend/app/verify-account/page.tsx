"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { verifyEmail } from "@/services/auth-service";

export default function VerifyAccountPage() {
  const [message, setMessage] = useState("Verifying your account...");
  const [isSuccess, setIsSuccess] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const uid = params.get("uid") ?? "";
    const token = params.get("token") ?? "";

    if (!uid || !token) {
      setMessage("Verification link is invalid or missing required parameters.");
      return;
    }

    verifyEmail({ uid, token })
      .then((res) => {
        setMessage(res.message || "Your account is verified. You can now sign in.");
        setIsSuccess(true);
      })
      .catch((err) => {
        setMessage(err instanceof Error ? err.message : "This verification link is invalid or expired.");
        setIsSuccess(false);
      });
  }, []);

  return <main className="shell"><div className="panel"><div className="brand">WillChain SL</div><h2>Account verification</h2><p>{message}</p><div className="inline"><Link href="/login">Go to sign in</Link></div></div></main>;
}
