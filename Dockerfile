FROM python:3.8-alpine

# Install dependencies
RUN apk add --no-cache gcc libffi-dev musl-dev

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
CMD [ "python", "./app.py", "-c", "/config"]