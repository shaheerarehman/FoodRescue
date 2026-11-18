# FoodRescue

FoodRescue is a FastAPI web application that connects businesses with surplus food to registered charities and nonprofit organizations.

Businesses can create time-sensitive food donation listings, while charities can view available donations, reserve them, and access pickup location information.

## Features

- Create food donation listings
- View available donations
- Reserve donations for a charity
- Manage donation status
- Automatically release two-hour reservations and expire donations past their pickup deadline
- Accept donations during geocoding outages and retry pending lookups
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

### Geocoding

`GEOCODING_PROVIDER=google` is the default and uses `GOOGLE_MAPS_API_KEY`.
`GEOCODING_PROVIDER=simulated` generates repeatable Hamilton-area coordinates locally for demonstrations. The web UI labels these as simulated and directs users to the pickup address. Select the provider before starting the app and worker. The wiring module selects the implementation and injects it into the shared donation service.

During a provider outage, a donation is saved as `AVAILABLE` with its address and `geocoding_status=PENDING`. It can be reserved immediately. The geocoding job retries active, pending donations after a five-minute delay between attempts. A definitive no-match is recorded as `NO_MATCH`. Previously stored coordinates remain as written. Use a separate demo table for simulated mode so simulated coordinates stay out of production.

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
DYNAMODB_TABLE=FoodRescueDonationsDev
GEOCODING_PROVIDER=simulated
```

Use AWS credentials scoped to a development table with a string partition key named `donation_id`. To create a new development table, verify the configured account, region, and table name, then run `python create_table.py`. Set the provider to `google` and supply an API key for a Google-mode demo.

Do not commit `.env` or AWS credentials to Git.

### 4. Run the application

```bash
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`.

FastAPI API documentation is available at `http://127.0.0.1:8000/docs`.

## Maintenance and tests

Run the offline tests with `python -m pytest`. To exercise one maintenance pass against the configured **development** table, use these commands from the application directory.

```bash
python -m maintenance expire
python -m maintenance geocode
```

The expiry job runs independently of web requests. A reservation can be picked up until the earlier of two hours from reservation or the pickup deadline. On the next scheduled pass, it returns to `AVAILABLE` if the pickup window remains open, or becomes `EXPIRED` if the pickup deadline has passed. A release clears the claim. The original request-time cleanup of overdue available listings still runs. Offset-free pickup deadlines retain the EC2 host's local timezone interpretation. Use consistent host timezones and clock synchronization, and prefer explicit offsets in new API inputs.

Older reservations have no reliable reservation time. The first expiry pass grants them a two-hour window from observation, subject to their pickup deadline. When a reservation times out with an unparseable deadline, the job expires the donation. DynamoDB conditional writes protect newly reserved items from stale expiry jobs and coordinate retries across hosts. The jobs use paginated scans and retry up to eight geocodes per pass per host. Runtime, scan cost, and scheduling lag grow with the table and backlog. The one-minute schedule assumes a running EC2 instance and healthy DynamoDB access.

## AWS deployment

The existing ALB, EC2 web service, ASG, S3 bundle, and DynamoDB table can continue to serve the app. No table migration or additional AWS service is required. The supplied archive does not contain the actual AMI bootstrap or web service definition, so verify the path, user, interpreter, environment, and permissions on staging first.

1. Deploy the application files and install `requirements.txt` in the existing web service environment. Configure both the app and maintenance jobs for the same table, region, and provider. For Google, verify outbound HTTPS access and a key authorized for the Geocoding API. The instance role needs `dynamodb:Scan` and `dynamodb:UpdateItem` for the worker on that table, in addition to the web app's existing access.
2. Adapt the supplied service unit's `User`, `WorkingDirectory`, and `ExecStart` to match the deployed app. The examples use `foodrescue` and `/opt/foodrescue/.venv/bin/python`. The worker loads the project's `.env`. If the web unit instead supplies environment variables, configure the same environment for the worker. The worker user must be able to read the configuration and run the interpreter.
3. Add the unit installation and timer enablement to the **AMI or launch bootstrap** so future ASG instances run the jobs. Enable the timers after the bundle and environment are available. Roll out the updated web code across the fleet before allowing the expiry timer to release reservations because older web instances only guard lifecycle writes by status.

   ```bash
   sudo install -m 644 deploy/foodrescue-maintenance@.service /etc/systemd/system/
   sudo install -m 644 deploy/foodrescue-maintenance@.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now foodrescue-maintenance@expire.timer foodrescue-maintenance@geocode.timer
   systemctl list-timers 'foodrescue-maintenance@*'
   sudo journalctl -u foodrescue-maintenance@expire.service -u foodrescue-maintenance@geocode.service
   ```

4. On staging, verify the existing web health check and create/reserve flows. Confirm a replacement instance starts both timers. On a development table, verify that a due reservation releases without an HTTP request and that a pending geocode resolves after provider recovery.

The existing GitHub Actions workflow uploads the source bundle and triggers an ASG refresh on a push to `main`. It does not install systemd units by itself. The submission ZIP wraps the source in a `FoodRescue/` directory. Build the existing deployment bundle from **inside** that directory if deploying manually.

See the [systemd timer reference](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html) and [DynamoDB Scan guide](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Scan.html).

## Security

- AWS credentials are not stored in the Git repository.
- EC2 accesses DynamoDB through an IAM instance role.
- `.env` is excluded from Git.
- Application instances accept application traffic from the load balancer rather than exposing port 8000 directly to the public internet.

## Project

Developed for SFWRTECH 4SA3 - Software Architecture.
