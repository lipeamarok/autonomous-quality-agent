.PHONY: setup test run-plan lint build demo install

# Setup environment
setup:
	@echo "Installing Python dependencies..."
	@pip install -r brain/requirements.txt
	@echo "Setup complete."

# Install AQA CLI
install:
	@echo "Installing AQA CLI..."
	@cd brain && pip install -e .
	@echo "AQA CLI installed. Run 'aqa --help' to get started."

# Build Runner (Release mode)
build:
	@echo "Building Runner (Release)..."
	@cd runner && cargo build --release

# Full demo: Generate plan + Execute with Runner
demo: build install
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║       🧪 AQA Demo - Autonomous Quality Agent                 ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📋 Step 1: Generating test plan with Brain..."
	@cd brain && python -m src.cli.main demo --save ../output/demo_plan.json --dry-run
	@echo ""
	@echo "🦀 Step 2: Executing plan with Runner..."
	@./runner/target/release/runner execute --file output/demo_plan.json
	@echo ""
	@echo "✅ Demo complete!"
	@echo "   - Plan saved: output/demo_plan.json"
	@echo "   - Report: output/report.json (if generated)"
	@echo ""

# Quick demo (dry-run only, no execution)
demo-dry: install
	@echo "🧪 AQA Demo (Dry Run)..."
	@cd brain && python -m src.cli.main demo --dry-run

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
