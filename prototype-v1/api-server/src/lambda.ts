// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0

import serverless from 'serverless-http';
import { app } from './server';

// Export serverless handler
export const handler = serverless(app);
