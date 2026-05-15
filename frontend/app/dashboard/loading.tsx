import { LoadingTips } from "@/components/LoadingTips";

export default function DashboardLoading() {
  return (
    <div className="loader-page">
      <LoadingTips label="Loading profile signal" />
    </div>
  );
}
