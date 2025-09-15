import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { JobProgress } from "@/types/mqtt";
import { Clock, CheckCircle, XCircle, Loader2 } from "lucide-react";

interface JobCardProps {
  job: JobProgress;
}

export const JobCard = ({ job }: JobCardProps) => {
  const getStatusIcon = () => {
    switch (job.state) {
      case "SUCCEEDED":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "FAILED":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "RUNNING":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = () => {
    switch (job.state) {
      case "SUCCEEDED":
        return "bg-green-500";
      case "FAILED":
        return "bg-red-500";
      case "RUNNING":
        return "bg-blue-500";
      default:
        return "bg-gray-500";
    }
  };

  const mapProgress =
    job.totalMaps > 0 ? (job.completedMaps / job.totalMaps) * 100 : 0;
  const reduceProgress =
    job.totalReduces > 0 ? (job.completedReduces / job.totalReduces) * 100 : 0;
  const overallProgress =
    ((job.completedMaps + job.completedReduces) /
      (job.totalMaps + job.totalReduces)) *
      100 || 0;

  const formatDuration = (start: number, end?: number) => {
    const duration = (end || Date.now()) - start;
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{job.jobId}</CardTitle>
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <Badge className={getStatusColor()}>{job.state}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between text-sm text-muted-foreground mb-1">
              <span>Overall Progress</span>
              <span>{Math.round(overallProgress)}%</span>
            </div>
            <Progress value={overallProgress} className="h-2" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex justify-between text-sm text-muted-foreground mb-1">
                <span>Map Tasks</span>
                <span>
                  {job.completedMaps}/{job.totalMaps}
                </span>
              </div>
              <Progress value={mapProgress} className="h-1" />
            </div>

            <div>
              <div className="flex justify-between text-sm text-muted-foreground mb-1">
                <span>Reduce Tasks</span>
                <span>
                  {job.completedReduces}/{job.totalReduces}
                </span>
              </div>
              <Progress value={reduceProgress} className="h-1" />
            </div>
          </div>

          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Duration: {formatDuration(job.startTime, job.endTime)}</span>
            <span>Started: {new Date(job.startTime).toLocaleTimeString()}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
