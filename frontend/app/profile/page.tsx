"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";
import { ArrowLeft, Camera, CheckCircle2, KeyRound, Mail, Phone, ShieldCheck, UserRound, X } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { changePassword, getProfile, updateProfile } from "@/services/auth-service";
import type { User } from "@/types/auth";

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/api\/v1\/?$/, "");

function avatarUrl(url: string | null) {
  if (!url) return "";
  return url.startsWith("http") ? url : `${API_ORIGIN}${url}`;
}

export default function ProfilePage() {
  const router = useRouter();
  const { user: authUser, initialLoading, refreshUser } = useAuth();

  const [user, setUser] = useState<User | null>(null);
  const [form, setForm] = useState({ first_name: "", last_name: "", phone_number: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraStream = useRef<MediaStream | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);

  // Password change state
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", new_password_confirmation: "" });
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

  // Authentication guard
  useEffect(() => {
    if (!initialLoading && !authUser) {
      router.push("/login");
    }
  }, [initialLoading, authUser, router]);

  useEffect(() => {
    getProfile().then(({ data }) => {
      setUser(data);
      setForm({ first_name: data.first_name, last_name: data.last_name, phone_number: data.phone_number });
      setAvatarPreview(avatarUrl(data.avatar));
    }).catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Profile could not be loaded."));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const payload = new FormData();
      payload.append("first_name", form.first_name);
      payload.append("last_name", form.last_name);
      payload.append("phone_number", form.phone_number);
      if (avatarFile) payload.append("avatar", avatarFile);
      const response = await updateProfile(payload);
      setUser(response.data);
      setAvatarPreview(avatarUrl(response.data.avatar) || avatarPreview);
      setAvatarFile(null);
      setMessage("Profile updated.");
      await refreshUser();
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Profile could not be updated.");
    }
  }

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordError("");
    setPasswordMessage("");
    setPasswordBusy(true);
    try {
      const response = await changePassword(passwordForm);
      setPasswordMessage(response.message || "Password changed successfully.");
      setPasswordForm({ current_password: "", new_password: "", new_password_confirmation: "" });
    } catch (changeErr) {
      setPasswordError(changeErr instanceof Error ? changeErr.message : "Password could not be changed.");
    } finally {
      setPasswordBusy(false);
    }
  }

  function selectAvatar(file?: File) {
    if (!file || !file.type.startsWith("image/")) return;
    setAvatarFile(file);
    setAvatarPreview(URL.createObjectURL(file));
    setMessage("");
  }

  async function openCamera() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera access is not available in this browser. Choose an image file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      cameraStream.current = stream;
      setCameraOpen(true);
      requestAnimationFrame(() => {
        if (videoRef.current) videoRef.current.srcObject = stream;
      });
    } catch {
      setError("Camera access was blocked. Allow camera permission in your browser or choose an image file instead.");
    }
  }

  function closeCamera() {
    cameraStream.current?.getTracks().forEach((track) => track.stop());
    cameraStream.current = null;
    setCameraOpen(false);
  }

  function capturePhoto() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) selectAvatar(new File([blob], "profile-photo.jpg", { type: "image/jpeg" }));
      closeCamera();
    }, "image/jpeg", 0.9);
  }

  useEffect(() => () => cameraStream.current?.getTracks().forEach((track) => track.stop()), []);

  const initials = `${form.first_name.charAt(0)}${form.last_name.charAt(0)}`.toUpperCase() || "WC";

  return (
    <main className="profile-page">
      <header className="profile-header"><Link href="/dashboard" className="profile-brand"><span className="profile-brand-mark"><ShieldCheck size={17} /></span> WILLCHAIN SL</Link><Link href="/dashboard" className="profile-back"><ArrowLeft size={15} /> Dashboard</Link></header>
      <section className="profile-content">
        <div className="profile-heading"><div><p className="profile-eyebrow">Account settings</p><h1>Account profile</h1><p className="profile-intro">Keep your identity details current for secure, accountable access.</p></div><div className="profile-status"><CheckCircle2 size={17} /> {user?.account_status ?? "Loading"}</div></div>
        {error && <div className="profile-alert">{error}</div>}
        {message && <div className="profile-success" role="status">{message}</div>}
        <div className="profile-layout">
          <aside className="profile-card profile-summary">
            <div className="avatar-wrap"><div className="avatar-image">{avatarPreview ? <img src={avatarPreview} alt="Profile" /> : <span>{initials}</span>}</div><button className="avatar-button" type="button" onClick={openCamera} title="Take a profile photo"><Camera size={16} /></button></div>
            <div className="avatar-actions"><button type="button" onClick={openCamera}><Camera size={15} /> Take photo</button><button type="button" onClick={() => fileInput.current?.click()}><UserRound size={15} /> Choose file</button><input ref={fileInput} className="avatar-input" type="file" accept="image/*" onChange={(event) => selectAvatar(event.target.files?.[0])} /></div>
            <h2>{form.first_name || "Your name"} {form.last_name}</h2><p className="summary-role">{user?.role ?? "Account role"}</p><p className="summary-helper">Add a clear profile photo so your identity is easy to recognise during secure workflows.</p>
            <div className="summary-details"><span><Mail size={15} /> {user?.email ?? "Loading email"}</span><span><Phone size={15} /> {form.phone_number || "No phone added"}</span></div>
          </aside>
          <div className="flex flex-col gap-6">
            <div className="profile-card profile-form-card"><div className="card-heading"><div className="heading-icon"><UserRound size={18} /></div><div><h2>Personal details</h2><p>These details identify your account.</p></div></div><form className="profile-form" onSubmit={submit}>
              <label><span>Email address</span><input disabled value={user?.email ?? ""} /></label>
              <div className="profile-form-row"><label><span>First name</span><input required value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} /></label><label><span>Last name</span><input required value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} /></label></div>
              <label><span>Phone number</span><input type="tel" value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} placeholder="Optional" /></label>
              <div className="profile-form-actions"><p>Changes are recorded with your account activity.</p><button type="submit">Save profile</button></div>
            </form></div>

            <div className="profile-card profile-form-card"><div className="card-heading"><div className="heading-icon"><KeyRound size={18} /></div><div><h2>Change password</h2><p>Choose a strong password to keep your digital estate protected.</p></div></div>
            {passwordError && <div className="profile-alert mb-4">{passwordError}</div>}
            {passwordMessage && <div className="profile-success mb-4" role="status">{passwordMessage}</div>}
            <form className="profile-form" onSubmit={submitPassword}>
              <label><span>Current password</span><input required type="password" autoComplete="current-password" value={passwordForm.current_password} onChange={(event) => setPasswordForm({ ...passwordForm, current_password: event.target.value })} /></label>
              <div className="profile-form-row">
                <label><span>New password</span><input required type="password" autoComplete="new-password" value={passwordForm.new_password} onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })} /></label>
                <label><span>Confirm new password</span><input required type="password" autoComplete="new-password" value={passwordForm.new_password_confirmation} onChange={(event) => setPasswordForm({ ...passwordForm, new_password_confirmation: event.target.value })} /></label>
              </div>
              <div className="profile-form-actions"><p>Changing your password will revoke all other active sessions.</p><button type="submit" disabled={passwordBusy}>{passwordBusy ? "Updating..." : "Update password"}</button></div>
            </form></div>
          </div>
        </div>
      </section>
      {cameraOpen && <div className="camera-backdrop" role="dialog" aria-modal="true" aria-label="Take profile photo"><div className="camera-dialog"><div className="camera-dialog-heading"><div><h2>Take profile photo</h2><p>Position your face in the frame, then capture.</p></div><button type="button" onClick={closeCamera} aria-label="Close camera"><X size={18} /></button></div><video ref={videoRef} autoPlay playsInline muted className="camera-preview" /><canvas ref={canvasRef} className="camera-canvas" /><div className="camera-actions"><button type="button" className="camera-cancel" onClick={closeCamera}>Cancel</button><button type="button" className="camera-capture" onClick={capturePhoto}><Camera size={16} /> Capture photo</button></div></div></div>}
    </main>
  );
}
