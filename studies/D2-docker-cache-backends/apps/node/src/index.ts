import express from "express";
import pino from "pino";
import { z } from "zod";

const log = pino();
const app = express();
const Query = z.object({ n: z.coerce.number().int().min(0).default(1) });

// d2-change-line: 0
const BUILD = 0;

app.get("/", (req, res) => {
  const q = Query.parse(req.query);
  res.json({ ok: true, n: q.n, build: BUILD });
});

app.listen(3000, () => log.info("listening on 3000"));
