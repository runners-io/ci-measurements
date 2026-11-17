FROM golang:1.26-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /out/svc .

FROM debian:bookworm-slim
COPY --from=build /out/svc /usr/local/bin/svc
CMD ["svc"]
