# Duka - Django E-commerce Application

## Overview
Duka is a Django-based e-commerce application with a CI/CD pipeline using GitHub Actions, AWS ECR, and Kubernetes deployment. This is my first django project and I am doing it as a technical test for a top company in Kenya.

## Tech Stack
- Python 3.9
- Django
- PostgreSQL 13
- Docker
- Kubernetes
- AWS Services (ECR, ECS)
- GitHub Actions for CI/CD

## Prerequisites
- Python 3.9
- PostgreSQL
- Docker
- kubectl
- AWS CLI configured
- eksctl (for Kubernetes cluster management)

## Local Development Setup
1. Clone the repository
```bash
git clone <repository-url>
cd duka
```
2. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
3. Install dependencies
```bash
pip install -r requirements.txt
```
4. Set up environmental variables by creating .env file in project root and add:
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/duka
DJANGO_SETTINGS_MODULE=duka.settings
```
5. Run migrations
```bash
python manage.py migrate
```
6. Start development server
```bash
python manage.py runserver
```
7. Running tests
```bash
python manage.py test
```
## CI/CD Pipeline
The project includes a GitHub Actions workflow that:
1. Runs tests
2. Builds Docker image
3. Pushes to Amazon ECR
4. Deploys to Kubernetes cluster

## Pipeline Requirements
- AWS credentials configured in GitHub Secrets:

  - AWS_ACCESS_KEY_ID

  - AWS_SECRET_ACCESS_KEY
- KUBECONFIG for Kubernetes deployment
- PostgreSQL database for testing
## Deployment
The application is deployed using Kubernetes. Deployment configurations can be found in the k8s/ directory.
## Infrastructure Requirements
- AWS EKS cluster
- AWS ECR repository
- PostgreSQL database instance

## Docker
Build the docker image locally:
```bash
docker build -t duka-app .
```
Run the container:
```bash
docker run -p 8000:8000 duka-app
```
## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Create a pull request

# Contact Information
This project was done by Arthur Adinda Otieno as a fullfillment for the Savannah Informatics Mid Level backend development.
[LinkedIn](https://www.linkedin.com/in/arthur-adinda-3a1266120/)