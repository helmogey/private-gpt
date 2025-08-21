# start a fastapi server with uvicorn
#
#import uvicorn
#
#from private_gpt.main import app
#from private_gpt.settings.settings import settings
#from dotenv import load_dotenv
#
#load_dotenv()
#
# Set log_config=None to do not use the uvicorn logging configuration, and
# use ours instead. For reference, see below:
# https://github.com/tiangolo/fastapi/discussions/7457#discussioncomment-5141108
#uvicorn.run(app, host="0.0.0.0", port=settings().server.port, log_config=None)



# In private_gpt/__main__.py

# This MUST be the absolute first thing to run. It loads the .env file
# before any other part of the application can access environment variables.
from dotenv import load_dotenv
load_dotenv()

# Now that the environment is loaded, we can import the rest of the app
import uvicorn
from private_gpt.main import app
from private_gpt.settings.settings import settings

# Set log_config=None to do not use the uvicorn logging configuration, and
# use ours instead. For reference, see below:
# https://github.com/tiangolo/fastapi/discussions/7457#discussioncomment-5141108
uvicorn.run(app, host="0.0.0.0", port=settings().server.port, log_config=None)
