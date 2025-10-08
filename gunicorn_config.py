# Gunicorn config for low-spec NAS

# Number of worker processes
# Rule of thumb is (2 * number_of_cores) + 1
# Synology 220j has a 4-core CPU, but only 512MB RAM.
# Start with a conservative number to avoid memory issues.
workers = 1

# The socket to bind to.
# '0.0.0.0:8000' means listen on port 8000 on all network interfaces.
bind = '0.0.0.0:8000'

# The type of workers to use.
# The default 'sync' is fine for this application.
worker_class = 'sync'

# The maximum number of simultaneous clients.
# (2 * workers) + 1 is a good starting point.
worker_connections = 1000

# Timeout for workers in seconds.
# Default is 30. Increase to handle potentially slow I/O operations without worker timeouts.
timeout = 300

# Keep alive connections
keepalive = 5

# Logging
# Use '-' to log to stdout, which is standard for containers.
accesslog = '-'
errorlog = '-'
loglevel = 'info'
