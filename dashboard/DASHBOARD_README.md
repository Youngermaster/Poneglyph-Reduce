# Poneglyph MapReduce Dashboard

A real-time monitoring dashboard for the Poneglyph MapReduce distributed computing system.

## Features

### 🚀 Real-time Monitoring

- **Live Job Tracking**: Monitor MapReduce jobs as they execute
- **MQTT Integration**: Real-time updates via MQTT WebSocket connection
- **Progress Visualization**: See map and reduce task completion in real-time

### 📊 Comprehensive Dashboard

- **Job Overview**: Cards showing individual job progress with completion percentages
- **Statistics**: Total, running, completed, and failed job counts
- **Flow Visualization**: Interactive diagram showing the MapReduce pipeline
- **Live Logs**: Real-time MQTT message stream with color-coded event types

### 🎨 Modern UI

- **Responsive Design**: Works on desktop and mobile devices
- **Dark/Light Mode**: Follows system preferences
- **shadcn/ui Components**: Beautiful, accessible UI components
- **TailwindCSS**: Modern styling with excellent performance

## Architecture

The dashboard connects to your MapReduce cluster through:

1. **MQTT Broker (EMQX)**: Receives real-time events on WebSocket port 8083
2. **Master API**: HTTP endpoints for additional cluster information (future enhancement)

### MQTT Topics Monitored

- `gridmr/job/created` - New job submissions
- `gridmr/job/{jobId}/map/completed` - Map task completions
- `gridmr/job/{jobId}/reduce/completed` - Reduce task completions
- `gridmr/job/{jobId}/shuffle/partitions` - Shuffle phase information
- `gridmr/job/{jobId}/state` - Job state changes (SUCCEEDED, FAILED)

## Quick Start

### Using Docker (Recommended)

The dashboard is already configured in the main `docker-compose.yml`:

```bash
# Start the entire cluster including dashboard
docker-compose up

# Access the dashboard
open http://localhost:3000
```

### Development Mode

```bash
cd dashboard
pnpm install
pnpm dev
```

The development server will start on `http://localhost:5173`.

## Configuration

The dashboard uses environment variables for configuration:

- `VITE_MQTT_HOST`: MQTT broker hostname (default: localhost)
- `VITE_MQTT_PORT`: MQTT WebSocket port (default: 8083)
- `VITE_MASTER_API`: Master node API endpoint (default: http://localhost:8080)

For Docker deployments, these are set automatically in `docker-compose.yml`.

## Dashboard Sections

### 1. Overview Tab

- **Job Cards**: Individual progress cards for each MapReduce job
- **Progress Bars**: Visual representation of map and reduce task completion
- **Status Badges**: Job state indicators (RUNNING, SUCCEEDED, FAILED)
- **Timing Information**: Job duration and start times

### 2. Flow Visualization Tab

- **Interactive Diagram**: Visual representation of the MapReduce pipeline
- **Node States**: Color-coded nodes showing mapper, shuffle, and reducer status
- **Animated Edges**: Data flow visualization with animated connections
- **Master Node**: Central coordinator node

### 3. Real-time Logs Tab

- **Live Event Stream**: Real-time MQTT messages as they arrive
- **Event Categorization**: Color-coded message types
- **Detailed Information**: Comprehensive event data display
- **Auto-scroll**: Automatically shows latest messages

## Technologies Used

- **React 19** - Modern React with latest features
- **TypeScript** - Type-safe development
- **Vite** - Fast build tool and dev server
- **TailwindCSS** - Utility-first CSS framework
- **shadcn/ui** - Beautiful, accessible UI components
- **React Flow** - Interactive node-based diagrams
- **MQTT.js** - Real-time message streaming
- **Lucide React** - Beautiful icon set

## Development

### Project Structure

```
dashboard/
├── src/
│   ├── components/          # React components
│   │   ├── ui/             # shadcn/ui components
│   │   ├── JobCard.tsx     # Individual job display
│   │   ├── LogViewer.tsx   # Real-time log viewer
│   │   ├── MapReduceFlow.tsx # Flow visualization
│   │   └── ConnectionStatus.tsx # MQTT connection status
│   ├── hooks/
│   │   └── useMqtt.ts      # MQTT connection hook
│   ├── types/
│   │   └── mqtt.ts         # TypeScript interfaces
│   └── App.tsx             # Main application
├── Dockerfile              # Container configuration
└── package.json           # Dependencies and scripts
```

### Adding New Features

1. **New Event Types**: Extend `types/mqtt.ts` and update `useMqtt.ts`
2. **Additional UI Components**: Add to `components/` directory
3. **New Dashboard Sections**: Add tabs to main `App.tsx`

## Troubleshooting

### Connection Issues

1. **MQTT Connection Failed**

   - Verify EMQX is running: `docker ps | grep emqx`
   - Check WebSocket port 8083 is accessible
   - Ensure firewall allows the connection

2. **No Data Appearing**

   - Verify MapReduce jobs are running and generating events
   - Check MQTT topic subscriptions in browser dev tools
   - Ensure MQTT messages match expected format

3. **Performance Issues**
   - Monitor browser memory usage with large message volumes
   - Consider implementing message batching for high-throughput scenarios

### Docker Issues

1. **Container Won't Start**

   - Check for port conflicts: `lsof -i :3000`
   - Verify Node.js version compatibility
   - Check Docker logs: `docker logs dashboard`

2. **Build Failures**
   - Clear pnpm cache: `pnpm store prune`
   - Delete node_modules and reinstall: `rm -rf node_modules && pnpm install`

## Future Enhancements

- [ ] Historical job data and analytics
- [ ] Worker node health monitoring
- [ ] Job submission interface
- [ ] Performance metrics and charts
- [ ] Alert system for job failures
- [ ] Export functionality for job reports
- [ ] Multi-cluster support
- [ ] Custom dashboard layouts
- [ ] WebRTC for direct worker communication
- [ ] Grafana integration for advanced metrics
