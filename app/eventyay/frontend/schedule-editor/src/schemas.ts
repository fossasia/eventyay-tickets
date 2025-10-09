import { z } from 'zod';
z.config({ jitless: true });

// Helper function to transform title to a record
const toTitleRecord = (val: unknown): Record<string, string> => {
  if (val !== null && typeof val === 'object') {
    return val as Record<string, string>;
  }
  if (typeof val === 'string') {
    return { en: val };
  }
  return { en: '' };
};

export const SpeakerSchema = z.object({
  code: z.string(),
  name: z.string().nullable().transform(val => val ?? ''),
});

export const RoomSchema = z.object({
  id: z.number(),
  name: z.record(z.string(), z.string()).default({}),
  description: z.record(z.string(), z.string()).default({})
});

export const TrackSchema = z.object({
  id: z.number(),
  name: z.record(z.string(), z.string()).default({})
});

// Define availability entry schema
const AvailabilityEntrySchema = z.object({
  start: z.string(),
  end: z.string()
});

export const TalkSchema = z.object({
  id: z.number(),
  code: z.string().optional(),
  title: z.union([
    z.string(),
    z.record(z.string(), z.string())
  ]).transform(toTitleRecord),
  abstract: z.string().optional(),
  speakers: z.union([
    z.array(z.string()),
    z.array(z.object({ name: z.string() }))
  ]).transform(val => {
    // Transform to array of strings (speaker names) for consistency
    if (val.length === 0) return [];
    if (typeof val[0] === 'string') {
      return val as string[];
    }
    return (val as { name: string }[]).map(speaker => speaker.name);
  }).optional().default([]),
  room: z.union([
    z.number(),
    z.string().transform(val => parseInt(val, 10) || 0)
  ]).nullable().optional(),
  track: z.union([
    z.number(),
    z.string().transform(val => parseInt(val, 10) || 0)
  ]).nullable().optional(),
  start: z.string().nullable().optional(),
  end: z.string().nullable().optional(),
  state: z.string().optional(),
  updated: z.string().optional(),
  uncreated: z.boolean().optional(),
  availabilities: z.array(AvailabilityEntrySchema).optional().default([]),
  duration: z.number().optional()
});

export const WarningSchema = z.object({
  message: z.string(),
});

const WarningRecordSchema = z.record(z.string(), z.array(WarningSchema));

export const ScheduleSchema = z.object({
  version: z.nullable(z.string().nullable()),
  event_start: z.string(),
  event_end: z.string(),
  timezone: z.string(),
  locales: z.array(z.string()).default([]),
  rooms: z.array(RoomSchema).default([]),
  tracks: z.array(TrackSchema).default([]),
  speakers: z.array(SpeakerSchema).default([]),
  talks: z.array(TalkSchema).default([]),
  now: z.string().optional(),
  warnings: WarningRecordSchema.optional().default({})
});

export const AvailabilitySchema = z.object({
  rooms: z.record(z.string(), z.array(AvailabilityEntrySchema)).optional(),
  talks: z.record(z.string(), z.array(AvailabilityEntrySchema)).optional(),
});

export const WarningsSchema = z.record(z.string(), z.array(WarningSchema)).optional();

// Inferred types
export type AvailabilityEntry = z.infer<typeof AvailabilityEntrySchema>;
export type Speaker = z.infer<typeof SpeakerSchema>;
export type Room = z.infer<typeof RoomSchema>;
export type Track = z.infer<typeof TrackSchema>;
export type Talk = z.infer<typeof TalkSchema>;
export type Schedule = z.infer<typeof ScheduleSchema>;
export type Availability = z.infer<typeof AvailabilitySchema>;
export type Warnings = z.infer<typeof WarningsSchema>;
