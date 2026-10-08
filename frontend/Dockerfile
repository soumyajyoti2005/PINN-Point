FROM node:20-alpine

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
COPY contracts/ ../contracts/

# Build the frontend to static files
RUN npm run build

# Start a simple web server for the built files, or just run Vite preview
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
