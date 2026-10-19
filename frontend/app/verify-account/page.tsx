"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
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

  return <AuthShell eyebrow="Identity verification" title={isSuccess ? "Your account is verified." : "Account verification"} description={message}>
    <div className={`verification-result ${isSuccess ? "is-success" : ""}`} role="status">{message}</div>
    <Link className="verification-link" href="/login">Continue to sign in <span aria-hidden="true">→</span></Link>
  </AuthShell>;
}
