-frontend

git add frontend/
git commit -m "Update: Describe your frontend changes here"
git push

-backend

git add app/
git commit -m "Update: Describe your backend changes here"
git push

- deployment backend master commands

cd app
gcloud run deploy ai-marketing-backend --source . --region us-central1 \
--service-account=vertex-express@windy-gearbox-477912-q3.iam.gserviceaccount.com \
--set-env-vars="DATABASE_URL=postgresql://neondb_owner:npg_sd3YZqnlC6Sy@ep-misty-wildflower-adbeh1q9-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require,GOOGLE_PROJECT_ID=windy-gearbox-477912-q3,GOOGLE_LOCATION=us-central1" \
--allow-unauthenticated \
--clear-base-image