package store

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

type DB struct {
	SQL *sql.DB
}

func Connect(ctx context.Context, databaseURL string) (*DB, error) {
	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(20)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(30 * time.Minute)

	deadline := time.Now().Add(30 * time.Second)
	for {
		if err = db.PingContext(ctx); err == nil {
			break
		}
		if time.Now().After(deadline) {
			_ = db.Close()
			return nil, fmt.Errorf("ping database: %w", err)
		}
		time.Sleep(500 * time.Millisecond)
	}
	return &DB{SQL: db}, nil
}

func (d *DB) Close() error {
	return d.SQL.Close()
}
