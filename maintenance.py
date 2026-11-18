import argparse

from wiring import service


def main():
    parser = argparse.ArgumentParser(description='Run one FoodRescue maintenance pass.')
    parser.add_argument('job', choices=('expire', 'geocode'))
    args = parser.parse_args()
    donations = service()
    if args.job == 'expire':
        donations.expire_due_donations()
    else:
        donations.retry_geocoding()


if __name__ == '__main__':
    main()
