import { Github } from "lucide-react";
import { signInWithGithub } from "@/app/actions";
import { PendingButton } from "@/components/PendingButton";

export function GitHubSignInButton({ children }: { children: string }) {
  return (
    <form action={signInWithGithub}>
      <PendingButton pendingLabel="Opening GitHub...">
        <Github size={18} /> {children}
      </PendingButton>
    </form>
  );
}
