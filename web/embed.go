package web

import (
	"embed"
	"html/template"
	"io/fs"
)

//go:embed templates/*.html
var templateFS embed.FS

//go:embed static/*
var Static embed.FS

func Templates() (*template.Template, error) {
	return template.New("").Funcs(template.FuncMap{
		"js": func(s string) template.JS { return template.JS(s) },
	}).ParseFS(templateFS, "templates/*.html")
}

func StaticFS() (fs.FS, error) {
	return fs.Sub(Static, "static")
}
