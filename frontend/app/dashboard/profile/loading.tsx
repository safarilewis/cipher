import { LoadingTips } from "@/components/LoadingTips";

export default function DashboardProfileLoading() {
  return (
    <div className="loader-page">
      <LoadingTips label="Loading profile editor" />
    </div>
  );
}
