FROM nginx:alpine

RUN rm -rf /usr/share/nginx/html/*

COPY code/web_application/index.html /usr/share/nginx/html/index.html
COPY code/web_application/app.js /usr/share/nginx/html/app.js

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]