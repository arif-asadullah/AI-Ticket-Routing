# ---------- development stage ----------
FROM node:20-slim AS dev

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]

# ---------- production stage ----------
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM node:20-slim AS production

WORKDIR /app

RUN npm install -g serve

COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
