# JobHunter AI -- System Architecture

## Overview

JobHunter AI is a platform designed to automate the job search process.\
It continuously monitors job boards (including LinkedIn), filters
opportunities according to user preferences, and automatically generates
tailored resumes optimized for each job posting.

Core capabilities:

-   Monitor new job postings in near real-time
-   Match jobs to user profiles
-   Generate tailored resumes using AI
-   Notify users immediately when relevant jobs appear
-   Track job applications and interview status

------------------------------------------------------------------------

# High Level Architecture

                    ┌──────────────────┐
                    │   Frontend Web   │
                    │   Next.js/React  │
                    └────────┬─────────┘
                             │
                             │ REST API
                             │
                    ┌────────▼────────┐
                    │   Backend API   │
                    │  (FastAPI/Nest) │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    User Service      Job Monitoring        AI Engine
    Profiles & CV     Scrapers              Matching + Resume

         │                   │                   │
         ▼                   ▼                   ▼
     PostgreSQL           Queue               LLM Provider
     Redis Cache          Workers             Resume Generator

------------------------------------------------------------------------

# Technology Stack

## Backend

-   FastAPI (Python) or NestJS (Node.js)
-   REST API

## Frontend

-   Next.js
-   TailwindCSS

## Database

-   PostgreSQL

## Cache / Queue

-   Redis
-   BullMQ or Celery

## Scraping

-   Playwright

## AI

-   OpenAI API or other LLM provider
-   Embeddings for similarity matching

------------------------------------------------------------------------

# Core Services

## 1. User Service

### Responsibilities

-   User registration and authentication
-   Profile management
-   CV upload and parsing
-   Job search preferences

### Database Schema

### Users

  Field           Type
  --------------- -----------
  id              uuid
  email           string
  password_hash   string
  created_at      timestamp

### Profiles

  Field              Type
  ------------------ ----------
  user_id            uuid
  name               string
  location           string
  years_experience   int
  desired_roles      text\[\]
  salary_range       int

### CVs

  Field            Type
  ---------------- -----------
  id               uuid
  user_id          uuid
  file_path        string
  parsed_content   text
  created_at       timestamp

------------------------------------------------------------------------

# 2. Job Monitoring Service

This service continuously collects job postings from job boards.

Supported sources:

-   LinkedIn
-   Indeed
-   Glassdoor (future)

### Scheduler

Runs every 10 minutes.

### Workflow

1.  Open job search page
2.  Apply predefined filters
3.  Extract job listings
4.  Normalize data
5.  Store jobs in database
6.  Trigger matching process

### Jobs Table

  Field         Type
  ------------- -----------
  id            uuid
  title         string
  company       string
  location      string
  description   text
  source        string
  url           string
  created_at    timestamp

------------------------------------------------------------------------

# 3. Job Matching Engine

Purpose: determine how well a job fits a user's CV.

### Pipeline

1.  Extract required skills from job description
2.  Extract skills from CV
3.  Compute similarity score
4.  Identify missing skills

### Example Output

Match Score: 82%

Missing Skills: - Kubernetes - Kafka

### Table: job_matches

  Field            Type
  ---------------- -----------
  user_id          uuid
  job_id           uuid
  score            float
  missing_skills   text\[\]
  created_at       timestamp

------------------------------------------------------------------------

# 4. AI Resume Generator

Automatically generates a customized resume for each job.

### Input

-   User CV
-   Job description

### Pipeline

1.  Parse job requirements
2.  Extract relevant sections from original CV
3.  Rewrite experience to match job keywords
4.  Optimize for ATS systems

### Output

-   Tailored Resume (PDF)

### Table: generated_resumes

  Field        Type
  ------------ -----------
  id           uuid
  user_id      uuid
  job_id       uuid
  file_path    string
  created_at   timestamp

------------------------------------------------------------------------

# 5. Notification Service

Notifies the user when a strong job match is found.

### Trigger

    match_score > user_threshold

### Notification Channels

-   Email
-   Push notifications
-   Telegram / Slack (future)

### Example Message

New Job Match Found

Role: Backend Engineer\
Match Score: 87%

A tailored resume has been generated.

------------------------------------------------------------------------

# 6. Application Tracking

Users can track their job applications.

### Table: applications

  Field     Type
  --------- ------
  user_id   uuid
  job_id    uuid
  status    enum

### Status values

-   saved
-   applied
-   interview
-   rejected
-   offer

------------------------------------------------------------------------

# 7. AI Skill Gap Analyzer

Analyzes what skills the user is missing for target roles.

### Pipeline

1.  Collect jobs the user applied to
2.  Extract required skills
3.  Compare with user's CV

### Example Output

Missing Skills:

-   Docker
-   GraphQL
-   AWS

------------------------------------------------------------------------

# 8. Job Scraper Architecture

Scrapers run as background workers.

### Scraper Worker

Uses Playwright automation.

### Flow

1.  Open job search page
2.  Extract job listings
3.  Push job data into queue
4.  Parser worker processes jobs

### Queues

-   job_scraping_queue
-   job_parser_queue

------------------------------------------------------------------------

# 9. Matching Worker

Triggered when new jobs appear.

### Workflow

1.  Fetch user filters
2.  Compute similarity score
3.  Store match results
4.  Trigger resume generation

------------------------------------------------------------------------

# 10. AI Modules

## Resume Parser

Extracts:

-   skills
-   experience
-   education

## Job Parser

Extracts:

-   required skills
-   seniority level
-   technologies

------------------------------------------------------------------------

# 11. API Endpoints

## Authentication

POST /auth/register\
POST /auth/login

## CV

POST /cv/upload\
GET /cv

## Jobs

GET /jobs/matches\
GET /jobs/{id}

## Resume

POST /resume/generate\
GET /resume/{id}

------------------------------------------------------------------------

# 12. Data Flow

    User uploads CV
            │
            ▼
    CV parsed
            │
            ▼
    Jobs scraped
            │
            ▼
    Matching engine
            │
            ▼
    Score calculated
            │
            ▼
    Resume generated
            │
            ▼
    Notification sent

------------------------------------------------------------------------

# 13. Security

-   JWT authentication
-   Rate limiting
-   Encrypted CV storage
-   Secure file uploads

------------------------------------------------------------------------

# 14. Scalability

Workers can be scaled independently.

Worker types:

-   Scrapers
-   Matchers
-   Resume generators

Queues:

-   job_scraping_queue
-   matching_queue
-   resume_queue

------------------------------------------------------------------------

# 15. MVP Scope

Initial version should include:

1.  User registration
2.  CV upload
3.  LinkedIn job scraping
4.  Job matching
5.  Email notifications

Features to postpone:

-   Auto-apply to jobs
-   Networking suggestions
-   Advanced analytics

------------------------------------------------------------------------

# 16. Development Phases

### Phase 1

Authentication + CV upload

### Phase 2

Job scraper

### Phase 3

Matching engine

### Phase 4

Resume generator

### Phase 5

Notifications

------------------------------------------------------------------------

# 17. Repository Structure

    jobhunter-ai/

    backend/
      auth/
      users/
      jobs/
      matching/
      ai/
      notifications/

    workers/
      scraper/
      matcher/
      resume/

    frontend/

------------------------------------------------------------------------

# Future Features

-   Auto job applications
-   Interview question generator
-   Networking suggestions
-   Salary prediction
