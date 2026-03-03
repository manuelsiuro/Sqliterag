import { DatabaseOverview } from "./DatabaseOverview";
import { DatabaseActions } from "./DatabaseActions";

export function DatabasePanel() {
  return (
    <div className="space-y-6">
      <DatabaseOverview />
      <hr className="border-gray-800" />
      <DatabaseActions />
    </div>
  );
}
