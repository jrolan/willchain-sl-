"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function VerifyAccountPage() {
  const [message, setMessage] = useState("Verifying your account...");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    fetch(`${API_BASE_URL}/auth/verify-email/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ uid: params.get("uid"), token: params.get("token") }) })
      .then((response) => setMessage(response.ok ? "Your account is verified. You can sign in." : "This verification link is invalid or expired."))
      .catch(() => setMessage("Verification could not be completed."));
  }, []);

  return <main className="shell"><div className="panel"><div className="brand">WillChain SL</div><h2>Account verification</h2><p>{message}</p><div className="inline"><Link href="/login">Go to sign in</Link></div></div></main>;
}
