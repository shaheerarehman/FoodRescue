# FoodRescue

FoodRescue is a FastAPI web application that connects businesses with surplus food to registered charities and nonprofit organizations.

Businesses can create time-sensitive food donation listings, while charities can view available donations, reserve them, and access pickup location information.

## Features

- Create food donation listings
- View available donations
- Reserve donations for a charity
- Manage donation status
- Automatically expire donations after their pickup deadline
- View pickup locations using Google Maps
- REST API for accessing donation functionality
- Shared business logic between the web interface and REST API
- Cloud-based donation storage using Amazon DynamoDB

## Architecture

FoodRescue uses a modular architecture with responsibilities separated across the application:

- `app.py` - FastAPI controllers and web/REST routes
- `services.py` - application and business logic
- `repository.py` - DynamoDB data access
- `states.py` - State and Factory pattern implementations
- `models.py` - application data models
- `views.py` - HTML presentation
- `config.py` - application configuration
- `create_table.py` - DynamoDB table setup

## Design Patterns

### MVC

The application separates controllers, models, and presentation responsibilities. FastAPI route handlers act as controllers, application data is represented through models, and HTML presentation is handled separately.

### State Pattern

Donation lifecycle behaviour is represented using separate state classes.

Supported states include:

- Available
- Reserved
- Completed
- Expired

The State Pattern controls which transitions are valid for a donation.

### Factory Pattern

`DonationStateFactory` creates the appropriate state object based on the donation's current status.

## Two Interfaces

FoodRescue provides both a browser-based interface and a REST API.

For example:

- Web: `GET /donations`
- REST: `GET /api/donations`

Both interfaces call the same shared service method:

`DonationService.get_available_donations()`

This prevents duplication of the application's core availability logic.

## Cloud Services

### Amazon DynamoDB

FoodRescue stores donation information in an Amazon DynamoDB table named `FoodRescueDonations`.

### Google Maps Geocoding API

When a donation is created, its pickup address is sent to the Google Maps Geocoding API.

The returned latitude and longitude are stored with the donation and used to provide a View Location link.

## Scalability

FoodRescue is deployed on AWS using:

- Application Load Balancer
- EC2
- Auto Scaling Group
- Launch Template
- Amazon Machine Image (AMI)
- DynamoDB

The Auto Scaling Group is configured with:

- Minimum capacity: 1 instance
- Desired capacity: 1 instance
- Maximum capacity: 3 instances
- Target tracking based on 50% average CPU utilization

The Application Load Balancer routes incoming requests to healthy FoodRescue EC2 instances.

EC2 instances use an IAM role to access DynamoDB without storing AWS access keys on the server.

## Maintainability

The application is separated into focused modules for controllers, business logic, database access, state management, models, views, and configuration.

This allows individual parts of the application to be changed with less impact on unrelated components.

## Technology Stack

- Python
- FastAPI
- Uvicorn
- Amazon EC2
- Amazon DynamoDB
- AWS Application Load Balancer
- AWS Auto Scaling
- AWS IAM
- Google Maps Geocoding API
- HTML/CSS
- Boto3

## Local Setup

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file based on `.env.example`.

```env
AWS_REGION=ca-central-1
DYNAMODB_TABLE=FoodRescueDonations
GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_API_KEY
```

AWS credentials should be configured separately using the AWS CLI or an IAM role.

Do not commit `.env` or AWS credentials to Git.

### 4. Run the application

```bash
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

FastAPI API documentation is available at `http://127.0.0.1:8000/docs`.

## Deployment

The deployed application runs behind an AWS Application Load Balancer.

Production EC2 instances are managed by an Auto Scaling Group and created from the FoodRescue launch template.

Application instances automatically start the FastAPI server using a systemd service.

## Security

- AWS credentials are not stored in the Git repository.
- EC2 accesses DynamoDB through an IAM instance role.
- `.env` is excluded from Git.
- Application instances accept application traffic from the load balancer rather than exposing port 8000 directly to the public internet.

## Project

Developed for SFWRTECH 4SA3 - Software Architecture.
