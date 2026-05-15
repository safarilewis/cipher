import { LoadingTips } from "@/components/LoadingTips";

export default function GithubOnboardingLoading() {
  return (
    <div className="loader-page">
      <LoadingTips label="Loading GitHub setup" />
    </div>
  );
}
