# Kwork Integration

This module provides integration with the Kwork freelance platform, allowing automated monitoring of new orders and sending responses.

## Features

- **Real-time Order Monitoring**: Periodically checks for new Kwork orders
- **Smart Filtering**: Filters orders based on keywords, categories, and price ranges
- **Automated Responses**: Sends pre-configured responses to matching orders
- **Telegram Notifications**: Sends notifications about new orders to Telegram
- **Blacklist**: Prevents responding to the same order multiple times
- **CLI Interface**: Easy-to-use command line tools for management

## Configuration

### Environment Variables

Add these to your `.env` file:

```ini
# Kwork API
KWORK_TOKEN=your_kwork_api_token_here
POLL_INTERVAL=300  # Polling interval in seconds (default: 300)
```

### Database

The integration uses the following database tables:

- `kwork_orders`: Stores information about Kwork orders
- `kwork_replies`: Tracks our replies to orders
- `kwork_filters`: Stores filter criteria for order matching

## Usage

### CLI Commands

```bash
# Start the Kwork poller
python -m src.kwork.cli start

# Test Kwork API connection
python -m src.kwork.cli test-connection

# Create a new filter
python -m src.kwork.cli create-filter "Web Development" --keyword "python" --keyword "django" --min-price 1000

# List all filters
python -m src.kwork.cli list-filters

# Delete a filter
python -m src.kwork.cli delete-filter <filter_id>
```

### Programmatic Usage

```python
from src.kwork.service import KworkService
from src.kwork.models import KworkFilter

# Initialize the service
service = KworkService()

# Create a new filter
filter_ = await service.create_filter(
    name="Web Development",
    keywords=["python", "django", "fastapi"],
    categories=[1, 5, 10],  # Category IDs
    min_price=1000,
    max_price=50000
)

# Process new orders
await service.process_new_orders()
```

## Integration with Main Application

The Kwork poller is automatically started when the main application starts. It runs as a background task and checks for new orders at the specified interval.

## Error Handling

- API errors are logged and retried with exponential backoff
- Failed replies are stored in the database with error details
- Critical errors are reported via Telegram notifications

## Testing

Run the test script to verify the integration:

```bash
python scripts/test_kwork_api.py
```

## Security Considerations

- API tokens should be stored securely in environment variables
- Database connection strings should use proper authentication
- Regular backups of the database are recommended

## Troubleshooting

### Common Issues

1. **API Connection Errors**
   - Verify your KWORK_TOKEN is valid
   - Check your internet connection
   - Make sure the Kwork API is operational

2. **No Orders Found**
   - Check your filter criteria
   - Verify there are active orders matching your criteria
   - Check the logs for any errors

3. **Database Issues**
   - Make sure the database is running and accessible
   - Check database permissions
   - Run database migrations if needed

## License

This project is licensed under the MIT License.
