import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
    vus: 10,
    duration: '10s',
    thresholds: {
        http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    },
};

export default function () {
    let res = http.get('http://localhost:8080/api/space-weather/current');
    
    check(res, {
        'status is 200': (r) => r.status === 200,
        'has classification': (r) => r.json() && r.json().hasOwnProperty('classification'),
    });
    
    sleep(1);
}
