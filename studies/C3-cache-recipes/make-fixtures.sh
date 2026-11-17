#!/usr/bin/env bash
# Builds one small project per ecosystem, with a real lockfile, under ./fixtures/<ecosystem>/.
# Run once by .github/workflows/C3-fixtures.yml on ubuntu-24.04; the output is then committed, so every later run
# hashes the same lockfile bytes. Nothing here is timed.
set -euo pipefail
OUT="${1:-fixtures}"
rm -rf "$OUT"; mkdir -p "$OUT"
cd "$OUT"

# ---- Node: the same dependencies for npm, pnpm and yarn
NODE_PKG='{
  "name": "c3-node",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "express": "^4.21.0", "lodash": "^4.17.21", "axios": "^1.7.0", "react": "^18.3.0", "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0", "eslint": "^9.0.0", "jest": "^29.7.0", "webpack": "^5.95.0", "prettier": "^3.3.0"
  }
}'
mkdir npm pnpm yarn
echo "$NODE_PKG" | sed 's/c3-node/c3-npm/'  > npm/package.json
echo "$NODE_PKG" | sed 's/c3-node/c3-pnpm/' > pnpm/package.json
echo "$NODE_PKG" | sed 's/c3-node/c3-yarn/' > yarn/package.json
( cd npm  && npm install --package-lock-only --ignore-scripts )
( cd pnpm && npm install -g pnpm >/dev/null && pnpm install --lockfile-only --ignore-scripts )
( cd yarn && yarn install --ignore-scripts --non-interactive >/dev/null && rm -rf node_modules )

# ---- Python
mkdir pip poetry
python3 -m venv /tmp/venv-pip
/tmp/venv-pip/bin/pip install --quiet requests flask numpy pandas pytest
/tmp/venv-pip/bin/pip freeze > pip/requirements.txt
cat > poetry/pyproject.toml <<'TOML'
[tool.poetry]
name = "c3-poetry"
version = "1.0.0"
description = "cache recipe fixture"
authors = ["ci-measurements <noreply@example.com>"]
package-mode = false

[tool.poetry.dependencies]
python = ">=3.10,<4.0"
requests = "^2.32"
flask = "^3.0"
numpy = "^2.0"
pandas = "^2.2"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3"
TOML
pipx install poetry >/dev/null
( cd poetry && poetry lock )

# ---- JVM
JAVA_SRC='public class App { public static void main(String[] a) { System.out.println(com.google.common.base.Joiner.on(",").join("c3", "ok")); } }'
mkdir -p gradle/src/main/java maven/src/main/java
echo "$JAVA_SRC" > gradle/src/main/java/App.java
echo "$JAVA_SRC" > maven/src/main/java/App.java
cat > gradle/settings.gradle <<'G'
rootProject.name = 'c3-gradle'
G
cat > gradle/build.gradle <<'G'
plugins { id 'java' }
repositories { mavenCentral() }
dependencies {
    implementation 'com.google.guava:guava:33.3.1-jre'
    implementation 'org.apache.commons:commons-lang3:3.17.0'
    implementation 'com.fasterxml.jackson.core:jackson-databind:2.18.0'
    testImplementation 'org.junit.jupiter:junit-jupiter:5.11.2'
}
G
( cd gradle && gradle wrapper --no-daemon -q )
cat > maven/pom.xml <<'X'
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>io.runners.c3</groupId>
  <artifactId>c3-maven</artifactId>
  <version>1.0.0</version>
  <properties>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
  <dependencies>
    <dependency><groupId>com.google.guava</groupId><artifactId>guava</artifactId><version>33.3.1-jre</version></dependency>
    <dependency><groupId>org.apache.commons</groupId><artifactId>commons-lang3</artifactId><version>3.17.0</version></dependency>
    <dependency><groupId>com.fasterxml.jackson.core</groupId><artifactId>jackson-databind</artifactId><version>2.18.0</version></dependency>
    <dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId><version>5.11.2</version><scope>test</scope></dependency>
  </dependencies>
</project>
X

# ---- Rust
mkdir -p cargo/src
cat > cargo/Cargo.toml <<'T'
[package]
name = "c3-cargo"
version = "1.0.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
regex = "1"
clap = { version = "4", features = ["derive"] }
rand = "0.8"
tokio = { version = "1", features = ["rt-multi-thread", "macros"] }
T
cat > cargo/src/main.rs <<'R'
use clap::Parser;
use serde::Serialize;

#[derive(Parser)]
struct Args {}

#[derive(Serialize)]
struct Out { ok: bool, n: u32 }

#[tokio::main]
async fn main() {
    let _ = Args::parse();
    let re = regex::Regex::new(r"c\d").unwrap();
    let n: u32 = rand::random::<u32>() % 10;
    println!("{} {}", re.is_match("c3"), serde_json::to_string(&Out { ok: true, n }).unwrap());
}
R
( cd cargo && cargo generate-lockfile )

# ---- Go
mkdir go
cat > go/main.go <<'G'
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
G
( cd go && go mod init c3go >/dev/null 2>&1 && go get github.com/spf13/cobra@v1.8.1 golang.org/x/text@v0.19.0 >/dev/null 2>&1 && go mod tidy )

# ---- Ruby
mkdir bundler
cat > bundler/Gemfile <<'G'
source "https://rubygems.org"
gem "sinatra"
gem "rake"
gem "rspec"
gem "rubocop"
gem "nokogiri"
G
( cd bundler && bundle lock )

# ---- .NET
mkdir nuget
SDK_MAJOR="$(dotnet --version | cut -d. -f1)"
cat > nuget/c3.csproj <<X
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net${SDK_MAJOR}.0</TargetFramework>
    <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
    <PackageReference Include="Serilog" Version="4.0.2" />
    <PackageReference Include="Dapper" Version="2.1.35" />
    <PackageReference Include="Polly" Version="8.4.2" />
  </ItemGroup>
</Project>
X
echo 'System.Console.WriteLine("c3");' > nuget/Program.cs
( cd nuget && dotnet restore --use-lock-file >/dev/null )

# ---- PHP
mkdir composer
cat > composer/composer.json <<'J'
{
  "name": "c3/composer",
  "require": {
    "monolog/monolog": "^3.7",
    "guzzlehttp/guzzle": "^7.9",
    "symfony/console": "^7.1",
    "symfony/yaml": "^7.1"
  },
  "require-dev": { "phpunit/phpunit": "^11.4" }
}
J
( cd composer && composer update --no-install --no-interaction --no-progress >/dev/null )

find . -maxdepth 2 -type f | sort
