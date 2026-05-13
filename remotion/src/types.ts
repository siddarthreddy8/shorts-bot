import { z } from "zod";

export const captionSchema = z.object({
  word: z.string(),
  startMs: z.number(),
  endMs: z.number(),
});

export type Caption = z.infer<typeof captionSchema>;
