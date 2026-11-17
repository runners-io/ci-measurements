package main

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/prometheus/client_golang/prometheus"
	"go.uber.org/zap"
	"google.golang.org/grpc"
)

// d2-change-line: 0
const build = 0

func main() {
	log, _ := zap.NewProduction()
	defer log.Sync()
	_ = grpc.NewServer()
	_ = prometheus.NewRegistry()
	_ = pgxpool.Config{}
	r := gin.New()
	r.GET("/", func(c *gin.Context) { c.JSON(http.StatusOK, gin.H{"ok": true, "build": build}) })
	log.Info("listening")
	_ = r.Run(":8080")
}
