"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { getProfile, updateProfile } from "@/services/auth-service";
import type { User } from "@/types/auth";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [form, setForm] = useState({ first_name: "", last_name: "", phone_number: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getProfile().then(({ data }) => {
      setUser(data);
      setForm({ first_name: data.first_name, last_name: data.last_name, phone_number: data.phone_number });
    }).catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Profile could not be loaded."));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const response = await updateProfile(form);
      setUser(response.data);
      setMessage("Profile updated.");
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Profile could not be updated.");
    }
  }

  return (
    <main className="shell">
      <div className="panel">
        <div className="brand">WillChain SL / Profile</div>
        <h2>Account profile</h2>
        {message && <p>{message}</p>}
        {error && <div className="notice">{error}</div>}
        <form className="form" onSubmit={submit}>
          <label>Email<input disabled value={user?.email ?? ""} /></label>
          <label>First name<input required value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} /></label>
          <label>Last name<input required value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} /></label>
          <label>Phone<input value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} /></label>
          <button type="submit">Save profile</button>
        </form>
        <div className="inline"><Link href="/dashboard">Dashboard</Link><span className="muted">{user?.role ?? ""}</span></div>
      </div>
    </main>
  );
}
