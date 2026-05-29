"use server";

import { redirect } from "next/navigation";
import { signIn, signOut } from "@/auth";
import { backendFetch } from "@/lib/backend";

export async function signInWithGithub() {
  await signIn("github", { redirectTo: "/onboarding/github" });
}

export async function signOutUser() {
  await signOut({ redirectTo: "/" });
}

export async function connectGithub(formData: FormData) {
  const username = String(formData.get("username") ?? "");
  const accessToken = String(formData.get("accessToken") ?? "");
  await backendFetch("/sources/github", {
    method: "POST",
    body: JSON.stringify({ username, access_token: accessToken || undefined })
  });
  redirect("/onboarding/leetcode");
}

export async function connectLeetcode(formData: FormData) {
  const username = String(formData.get("username") ?? "");
  await backendFetch("/sources/leetcode", {
    method: "POST",
    body: JSON.stringify({ username })
  });
  redirect("/onboarding/profile");
}

export async function saveProfileSection(formData: FormData) {
  await backendFetch("/profile/sections", {
    method: "POST",
    body: JSON.stringify({
      kind: formData.get("kind"),
      title: formData.get("title"),
      organization: formData.get("organization") || null,
      start_date: formData.get("startDate") || null,
      end_date: formData.get("endDate") || null,
      description: formData.get("description") || null,
      url: formData.get("url") || null,
      order: Number(formData.get("order") || 0)
    })
  });
  redirect("/dashboard");
}

export async function updateProfileSection(formData: FormData) {
  const id = String(formData.get("id"));
  await backendFetch(`/profile/sections/${id}`, {
    method: "PUT",
    body: JSON.stringify({
      kind: formData.get("kind"),
      title: formData.get("title"),
      organization: formData.get("organization") || null,
      start_date: formData.get("startDate") || null,
      end_date: formData.get("endDate") || null,
      description: formData.get("description") || null,
      url: formData.get("url") || null,
      order: Number(formData.get("order") || 0)
    })
  });
  redirect("/dashboard/profile");
}

export async function deleteProfileSection(formData: FormData) {
  const id = String(formData.get("id"));
  const redirectTo = String(formData.get("redirectTo") ?? "/dashboard/profile");
  await backendFetch(`/profile/sections/${id}`, { method: "DELETE" });
  redirect(redirectTo);
}

export async function updateProfileBasics(formData: FormData) {
  await backendFetch("/profile", {
    method: "PATCH",
    body: JSON.stringify({
      name: formData.get("name") || null,
      headline: formData.get("headline") || null,
      slug: formData.get("slug") || null
    })
  });
  redirect("/dashboard");
}

export async function deleteSource(formData: FormData) {
  const kind = String(formData.get("kind"));
  await backendFetch(`/sources/${kind}`, { method: "DELETE" });
  redirect("/dashboard/sources");
}

export async function saveRepositorySelection(formData: FormData) {
  const repositoryIds = formData.getAll("repositoryIds").map(String);
  await backendFetch("/sources/github/repositories/selection", {
    method: "POST",
    body: JSON.stringify({ repository_ids: repositoryIds })
  });
  redirect("/dashboard/sources");
}

export async function createAnalysis() {
  let errorMessage: string | null = null;

  try {
    await backendFetch("/analysis", { method: "POST" });
  } catch (error) {
    errorMessage = error instanceof Error ? error.message : "Analysis failed";
  }

  if (errorMessage) {
    redirect(`/dashboard/analysis?error=${encodeURIComponent(errorMessage)}`);
  }

  redirect("/dashboard/analysis");
}

export async function reviewAnalysis(formData: FormData) {
  const id = String(formData.get("id"));
  await backendFetch(`/analysis/${id}/review`, { method: "POST" });
  redirect("/dashboard/analysis");
}

export async function publishProfile() {
  await backendFetch("/analysis/publish", { method: "POST" });
  redirect("/dashboard");
}

export async function unpublishProfile() {
  await backendFetch("/analysis/unpublish", { method: "POST" });
  redirect("/dashboard");
}
