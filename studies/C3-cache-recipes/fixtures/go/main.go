package main

import (
	"fmt"

	"github.com/spf13/cobra"
	"golang.org/x/text/cases"
	"golang.org/x/text/language"
)

func main() {
	cmd := &cobra.Command{Use: "c3", Run: func(*cobra.Command, []string) {
		fmt.Println(cases.Title(language.English).String("c3 ok"))
	}}
	_ = cmd.Execute()
}
