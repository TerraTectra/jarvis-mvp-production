#!/bin/bash
# Run CI checks in a Docker container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
IMAGE_NAME="jarvis-mvp-ci"
CONTAINER_NAME="jarvis-mvp-ci-runner"
VOLUME_MOUNT="$(pwd):/app"
WORKDIR="/app"
PYTHON_VERSION="3.9"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --python-version)
            PYTHON_VERSION="$2"
            shift 2
            ;;
        --image-name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --container-name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --volume)
            VOLUME_MOUNT="$2"
            shift 2
            ;;
        --workdir)
            WORKDIR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Run CI checks in a Docker container"
            echo ""
            echo "Options:"
            echo "  --python-version VERSION  Python version to use (default: 3.9)"
            echo "  --image-name NAME        Docker image name (default: jarvis-mvp-ci)"
            echo "  --container-name NAME    Container name (default: jarvis-mvp-ci-runner)"
            echo "  --volume MOUNT           Volume mount (default: $(pwd):/app)"
            echo "  --workdir DIR            Working directory in container (default: /app)"
            echo "  --help                   Show this help message and exit"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${YELLOW}🚀 Starting CI checks in Docker...${NC}"
echo -e "  Python version: ${PYTHON_VERSION}"
echo -e "  Image name: ${IMAGE_NAME}"
echo -e "  Container name: ${CONTAINER_NAME}"
echo -e "  Volume mount: ${VOLUME_MOUNT}"
echo -e "  Working directory: ${WORKDIR}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker and try again.${NC}"
    exit 1
fi

# Build the Docker image if it doesn't exist
if ! docker image inspect "${IMAGE_NAME}:latest" &> /dev/null; then
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker build \
        --build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
        -t "${IMAGE_NAME}:latest" \
        -f ci/Dockerfile.ci .
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${GREEN}✓ Using existing Docker image: ${IMAGE_NAME}${NC}"
fi

# Create logs directory if it doesn't exist
mkdir -p ci/logs

# Run the CI checks in the container
echo -e "\n${YELLOW}Running CI checks...${NC}"
set +e  # Don't exit on error to ensure cleanup runs

docker run \
    --rm \
    --name "${CONTAINER_NAME}" \
    -v "${VOLUME_MOUNT}" \
    -w "${WORKDIR}" \
    -e PYTHONPATH="/app" \
    -e CI="true" \
    -e PIP_CACHE_DIR="/tmp/pip-cache" \
    -v "${PWD}/ci/logs:/app/ci/logs" \
    --entrypoint "/bin/bash" \
    "${IMAGE_NAME}:latest" \
    -c "
        echo '🚀 Starting CI checks...' && \
        echo 'Python version:' && python --version && \
        echo 'pip version:' && pip --version && \
        echo 'Installing dependencies...' && \
        pip install -e .[dev] && \
        echo '\n🔍 Running checks...' && \
        python ci/run_ci.py -v
    "

EXIT_CODE=$?

# Print a summary
echo -e "\n${YELLOW}=== CI Checks Summary ===${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
else
    echo -e "${RED}❌ Some checks failed. See logs above for details.${NC}"
    
    # Show the last few lines of the log file if it exists
    LOG_FILE="ci/logs/ci_$(date +%Y%m%d).log"
    if [ -f "$LOG_FILE" ]; then
        echo -e "\n${YELLOW}=== Tail of CI Log ===${NC}"
        tail -n 20 "$LOG_FILE"
        echo -e "\nFull log: $LOG_FILE"
    fi
fi

echo -e "\n🎉 CI checks completed with exit code: ${EXIT_CODE}"
exit $EXIT_CODE
