import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { MqttMessage } from "../types/mqtt";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AlertCircle, CheckCircle, Info, Shuffle } from "lucide-react";

interface LogViewerProps {
  messages: MqttMessage[];
}

export const LogViewer = ({ messages }: LogViewerProps) => {
  const getMessageIcon = (type: string) => {
    switch (type) {
      case "job/created":
        return <Info className="h-4 w-4 text-blue-500" />;
      case "map/completed":
      case "reduce/completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "shuffle/partitions":
        return <Shuffle className="h-4 w-4 text-purple-500" />;
      case "job/state":
        return <AlertCircle className="h-4 w-4 text-orange-500" />;
      default:
        return <Info className="h-4 w-4 text-gray-500" />;
    }
  };

  const getMessageColor = (type: string) => {
    switch (type) {
      case "job/created":
        return "bg-blue-100 text-blue-800 border-blue-200";
      case "map/completed":
      case "reduce/completed":
        return "bg-green-100 text-green-800 border-green-200";
      case "shuffle/partitions":
        return "bg-purple-100 text-purple-800 border-purple-200";
      case "job/state":
        return "bg-orange-100 text-orange-800 border-orange-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const formatMessage = (message: MqttMessage) => {
    switch (message.type) {
      case "job/created":
        return `Job ${message.data.jobId} created with ${message.data.maps} map tasks and ${message.data.reducers} reducers`;
      case "map/completed":
        return `Map task ${message.data.taskId} completed (${message.data.mapsCompleted} total)`;
      case "reduce/completed":
        return `Reduce task ${message.data.taskId} completed (${message.data.reducesCompleted} total)`;
      case "shuffle/partitions":
        return `Shuffle phase: ${
          message.data.sizes.length
        } partitions with sizes [${message.data.sizes.join(", ")}]`;
      case "job/state":
        return `Job state changed to ${message.data.state}`;
      default:
        return "Unknown message type";
    }
  };

  return (
    <Card className="h-[400px]">
      <CardHeader>
        <CardTitle className="text-lg">Real-time Logs</CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[320px] w-full">
          <div className="space-y-2">
            {messages.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                No messages yet. Waiting for MQTT events...
              </div>
            ) : (
              messages.map((message, index) => (
                <div
                  key={index}
                  className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                >
                  <div className="flex-shrink-0 mt-0.5">
                    {getMessageIcon(message.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-1">
                      <Badge
                        variant="outline"
                        className={`text-xs ${getMessageColor(message.type)}`}
                      >
                        {message.type}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(
                          "ts" in message.data ? message.data.ts : Date.now()
                        ).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-sm text-foreground">
                      {formatMessage(message)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
};
