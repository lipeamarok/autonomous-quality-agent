.PHONY: setup test run-plan lint build

# Setup environment
setup:
	@echo "Installing Python dependencies..."
	@pip install -r brain/requirements.txt
	@echo "Setup complete."

# Build Runner (Release mode)
build:
	@echo "Building Runner (Release)..."
	@cd runner && cargo build --release

# Run the demo plan using the compiled runner
run-plan: build
	@echo "Running Demo Plan..."
	@./runner/target/release/runner execute --file schemas/examples/demo_plan.json

# Run all tests (Rust + Python)
test:
	@echo "Running Rust tests..."
	@cd runner && cargo test
	@echo "Running Python tests..."
	@pytest brain/tests

# Lint code
lint:
	@echo "Linting Rust..."
	@cd runner && cargo clippy
