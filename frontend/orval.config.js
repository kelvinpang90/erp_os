import { defineConfig } from 'orval';
export default defineConfig({
    erpOs: {
        input: {
            target: process.env.ORVAL_OPENAPI_URL ?? 'http://localhost:8000/openapi.json',
        },
        output: {
            mode: 'tags-split',
            target: 'src/api/generated',
            client: 'axios',
            httpClient: 'axios',
            override: {
                mutator: {
                    path: 'src/api/client.ts',
                    name: 'apiClient',
                },
            },
        },
    },
});
