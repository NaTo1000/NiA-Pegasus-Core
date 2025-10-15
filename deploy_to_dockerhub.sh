#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 Docker Hub Deployment Script for Switch Toolkit${NC}"
echo ""

# Get Docker Hub username
if [ -z "$DOCKER_USERNAME" ]; then
    read -p "Enter your Docker Hub username: " DOCKER_USERNAME
else
    echo -e "${GREEN}Using Docker Hub username: ${DOCKER_USERNAME}${NC}"
fi

# Set image name and version
IMAGE_NAME="switch-toolkit"
VERSION="${1:-1.0.0}"
LATEST_TAG="${DOCKER_USERNAME}/${IMAGE_NAME}:latest"
VERSION_TAG="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo ""
echo -e "${BLUE}📦 Building Docker image...${NC}"
echo "Image: ${IMAGE_NAME}"
echo "Version: ${VERSION}"
echo "Tags: ${VERSION_TAG}, ${LATEST_TAG}"
echo ""

# Build the Docker image
echo -e "${YELLOW}Building image...${NC}"
docker build -t ${IMAGE_NAME}:${VERSION} .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Build successful!${NC}"
echo ""

# Test the image locally
echo -e "${BLUE}🧪 Testing image locally...${NC}"
docker run --rm ${IMAGE_NAME}:${VERSION} --help 2>/dev/null || docker run --rm ${IMAGE_NAME}:${VERSION} vlan

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Local test failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Local test passed!${NC}"
echo ""

# Tag for Docker Hub
echo -e "${YELLOW}🏷️  Tagging images for Docker Hub...${NC}"
docker tag ${IMAGE_NAME}:${VERSION} ${VERSION_TAG}
docker tag ${IMAGE_NAME}:${VERSION} ${LATEST_TAG}

echo -e "${GREEN}✅ Images tagged${NC}"
echo ""

# Check if logged in to Docker Hub
echo -e "${BLUE}🔐 Checking Docker Hub login...${NC}"
docker info 2>/dev/null | grep -q "Username" || {
    echo -e "${YELLOW}Not logged in to Docker Hub. Logging in...${NC}"
    docker login --username ${DOCKER_USERNAME}
}

# Push to Docker Hub
echo ""
echo -e "${BLUE}📤 Pushing to Docker Hub...${NC}"
echo -e "${YELLOW}Pushing ${VERSION_TAG}...${NC}"
docker push ${VERSION_TAG}

echo -e "${YELLOW}Pushing ${LATEST_TAG}...${NC}"
docker push ${LATEST_TAG}

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 Successfully deployed to Docker Hub!${NC}"
    echo ""
    echo -e "${BLUE}📝 Your image is now available at:${NC}"
    echo -e "  ${GREEN}docker pull ${VERSION_TAG}${NC}"
    echo -e "  ${GREEN}docker pull ${LATEST_TAG}${NC}"
    echo ""
    echo -e "${BLUE}🚀 Run with:${NC}"
    echo -e "  ${GREEN}docker run -it --rm --network host ${LATEST_TAG}${NC}"
else
    echo -e "${RED}❌ Push failed!${NC}"
    exit 1
fi