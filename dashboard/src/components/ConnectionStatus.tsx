import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Wifi, WifiOff, AlertCircle } from "lucide-react";

interface ConnectionStatusProps {
  isConnected: boolean;
  error: string | null;
}

export const ConnectionStatus = ({
  isConnected,
  error,
}: ConnectionStatusProps) => {
  if (error) {
    return (
      <Alert className="mb-4 border-red-200 bg-red-50">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription className="text-red-800">
          MQTT Connection Error: {error}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="flex items-center space-x-2 mb-4">
      {isConnected ? (
        <>
          <Wifi className="h-4 w-4 text-green-500" />
          <Badge className="bg-green-500">Connected to MQTT</Badge>
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4 text-red-500" />
          <Badge className="bg-red-500">Disconnected</Badge>
        </>
      )}
    </div>
  );
};
