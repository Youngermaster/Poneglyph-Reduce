# Use Node.js 20 Alpine as base image
FROM node:20-alpine

# Set the working directory
WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Copy package.json and pnpm-lock.yaml
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy the rest of the application code
COPY . .

# Build the application
RUN pnpm build

# Expose the port
EXPOSE 5173

# Start the application
CMD ["pnpm", "preview", "--host", "0.0.0.0", "--port", "5173"]
