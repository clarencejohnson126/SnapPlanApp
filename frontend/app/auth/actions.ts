"use server";

import { redirect } from "next/navigation";

export type AuthResult = {
  error?: string;
  success?: boolean;
};

// Auth disabled for MVP - redirect to app directly
export async function login(formData: FormData): Promise<AuthResult> {
  redirect("/app");
}

export async function signup(formData: FormData): Promise<AuthResult> {
  redirect("/app");
}

export async function logout(): Promise<void> {
  redirect("/");
}
