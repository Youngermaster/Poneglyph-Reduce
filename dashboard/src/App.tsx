import "./App.css";
import { useMqtt } from "./hooks/useMqtt";
import { ConnectionStatus } from "./components/ConnectionStatus";
import { JobCard } from "./components/JobCard";
import { LogViewer } from "./components/LogViewer";
import { MapReduceFlow } from "./components/MapReduceFlow";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, BarChart3, FileText, Workflow } from "lucide-react";

function App() {
  const { isConnected, jobs, recentMessages, error } = useMqtt();

  const activeJobs = Array.from(jobs.values()).filter(
    (job) => job.state === "RUNNING"
  );
  const completedJobs = Array.from(jobs.values()).filter(
    (job) => job.state === "SUCCEEDED"
  );
  const failedJobs = Array.from(jobs.values()).filter(
    (job) => job.state === "FAILED"
  );

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Poneglyph MapReduce Dashboard
            </h1>
            <p className="text-muted-foreground">
              Real-time monitoring for distributed MapReduce cluster
            </p>
          </div>
          <ConnectionStatus isConnected={isConnected} error={error} />
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Jobs</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{jobs.size}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Running Jobs
              </CardTitle>
              <BarChart3 className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {activeJobs.length}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Completed Jobs
              </CardTitle>
              <FileText className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {completedJobs.length}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Failed Jobs</CardTitle>
              <Workflow className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">
                {failedJobs.length}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList>
            <TabsTrigger value="overview" className="text-white">
              Overview
            </TabsTrigger>
            <TabsTrigger value="flow" className="text-white">
              Flow Visualization
            </TabsTrigger>
            <TabsTrigger value="logs" className="text-white">
              Real-time Logs
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from(jobs.values())
                .sort((a, b) => b.startTime - a.startTime)
                .map((job) => (
                  <JobCard key={job.jobId} job={job} />
                ))}

              {jobs.size === 0 && (
                <Card className="col-span-full">
                  <CardContent className="flex items-center justify-center h-32">
                    <div className="text-center text-muted-foreground">
                      <Workflow className="h-8 w-8 mx-auto mb-2" />
                      <p>No jobs yet. Start a MapReduce job to see it here.</p>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </TabsContent>

          <TabsContent value="flow">
            <MapReduceFlow jobs={jobs} />
          </TabsContent>

          <TabsContent value="logs">
            <LogViewer messages={recentMessages} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default App;
