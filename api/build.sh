#!/bin/bash

# Nightly Rust.
rustup override set nightly

# Run database migrations.
cargo install sqlx-cli
sqlx migrate run

# Build.
cargo build --release

