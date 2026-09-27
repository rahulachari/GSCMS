'use client';

import React from 'react';
import { FlowButton } from './flow-button';

export const FlowButtonDemo = () => {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-100 dark:bg-black p-4">
      <FlowButton text="Flow Button" />
    </div>
  );
};

export default FlowButtonDemo;
