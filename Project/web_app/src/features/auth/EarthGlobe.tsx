import { useEffect, useRef, useState } from 'react';

const vertexSource = `
attribute vec2 a_position;
varying vec2 v_uv;
void main() {
  v_uv = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}`;

const fragmentSource = `
precision mediump float;
varying vec2 v_uv;
uniform sampler2D u_earth;
uniform vec2 u_resolution;
uniform float u_rotation;
uniform float u_time;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

void main() {
  vec2 uv = v_uv;
  vec2 p = (uv * 2.0 - 1.0) * vec2(u_resolution.x / u_resolution.y, 1.0);
  float radius = 0.76 * min(1.0, u_resolution.x / u_resolution.y);
  vec2 spherePoint = p / radius;
  float distanceFromCenter = dot(spherePoint, spherePoint);

  vec3 background = vec3(0.0196, 0.0235, 0.0353);
  float panelGlow = exp(-dot(p, p) * 0.72);
  background += vec3(0.003, 0.008, 0.03) * panelGlow;
  vec2 starCell = floor(uv * u_resolution / 3.0);
  float star = step(0.997, hash(starCell));
  float twinkle = 0.62 + 0.38 * sin(u_time * 1.7 + hash(starCell) * 6.28318);
  background += vec3(0.28, 0.38, 0.62) * star * twinkle;

  if (distanceFromCenter <= 1.0) {
    vec3 normal = normalize(vec3(spherePoint, sqrt(1.0 - distanceFromCenter)));
    vec3 lightDirection = normalize(vec3(-0.48, 0.24, 0.84));
    float daylight = dot(normal, lightDirection);
    float day = smoothstep(-0.18, 0.3, daylight);
    float longitude = atan(normal.z, normal.x) / 6.2831853 + 0.5 + u_rotation;
    float latitude = asin(normal.y) / 3.14159265 + 0.5;
    vec3 surface = texture2D(u_earth, vec2(fract(longitude), latitude)).rgb;
    surface *= 0.12 + 0.88 * day;
    surface += vec3(0.0, 0.028, 0.055) * (1.0 - day);
    float atmosphere = pow(1.0 - max(normal.z, 0.0), 3.2);
    surface += vec3(0.025, 0.19, 0.56) * atmosphere * 0.8;
    gl_FragColor = vec4(surface, 1.0);
  } else {
    float edgeDistance = abs(sqrt(distanceFromCenter) - 1.0);
    float halo = 1.0 - smoothstep(0.0, 0.095, edgeDistance);
    background += vec3(0.02, 0.13, 0.42) * halo * 0.37;
    gl_FragColor = vec4(background, 1.0);
  }
}`;

function compile(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error('Could not create globe shader.');
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const error = gl.getShaderInfoLog(shader) ?? 'Globe shader did not compile.';
    gl.deleteShader(shader);
    throw new Error(error);
  }
  return shader;
}

export function EarthGlobe() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [motion, setMotion] = useState(true);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext('webgl', { alpha: false, antialias: true, powerPreference: 'low-power' });
    if (!canvas || !gl) return;

    let frame = 0;
    let disposed = false;
    let rotation = 0;
    let program: WebGLProgram | null = null;
    let texture: WebGLTexture | null = null;
    let resizeObserver: ResizeObserver | null = null;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(media.matches);
    const startTime = performance.now();

    try {
      const vertex = compile(gl, gl.VERTEX_SHADER, vertexSource);
      const fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource);
      program = gl.createProgram();
      if (!program) throw new Error('Could not create globe program.');
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Could not link globe program.');
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
      gl.useProgram(program);

      const position = gl.createBuffer();
      if (!position) throw new Error('Could not create globe geometry.');
      gl.bindBuffer(gl.ARRAY_BUFFER, position);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
      const positionLocation = gl.getAttribLocation(program, 'a_position');
      gl.enableVertexAttribArray(positionLocation);
      gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

      texture = gl.createTexture();
      if (!texture) throw new Error('Could not create Earth texture.');
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([15, 56, 100, 255]));
      // NASA's 5400 × 2700 map is not power-of-two, so WebGL 1 requires clamp/linear sampling.
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.uniform1i(gl.getUniformLocation(program, 'u_earth'), 0);

      const image = new Image();
      image.src = '/earth-texture.jpg';
      image.onload = () => {
        if (disposed || !texture) return;
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, 1);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, image);
      };

      const resize = () => {
        const rect = canvas.getBoundingClientRect();
        const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
        const width = Math.max(1, Math.round(rect.width * ratio));
        const height = Math.max(1, Math.round(rect.height * ratio));
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width;
          canvas.height = height;
        }
        gl.viewport(0, 0, width, height);
      };
      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(canvas);
      resize();

      const draw = (now: number) => {
        if (disposed || !program) return;
        if (motion && !media.matches) rotation += 0.00042;
        gl.useProgram(program);
        gl.uniform2f(gl.getUniformLocation(program, 'u_resolution'), canvas.width, canvas.height);
        gl.uniform1f(gl.getUniformLocation(program, 'u_rotation'), rotation);
        gl.uniform1f(gl.getUniformLocation(program, 'u_time'), (now - startTime) / 1000);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
        if (motion && !media.matches) frame = window.requestAnimationFrame(draw);
      };
      draw(startTime);
      const onMotionChange = () => {
        setReducedMotion(media.matches);
        window.cancelAnimationFrame(frame);
        if (motion && !media.matches) frame = window.requestAnimationFrame(draw);
        else draw(performance.now());
      };
      media.addEventListener('change', onMotionChange);

      return () => {
        disposed = true;
        window.cancelAnimationFrame(frame);
        media.removeEventListener('change', onMotionChange);
        resizeObserver?.disconnect();
        if (texture) gl.deleteTexture(texture);
        if (program) gl.deleteProgram(program);
      };
    } catch {
      return () => {
        disposed = true;
        window.cancelAnimationFrame(frame);
        resizeObserver?.disconnect();
        if (texture) gl.deleteTexture(texture);
        if (program) gl.deleteProgram(program);
      };
    }
  }, [motion]);

  return <div className="earth-visual__globe">
    <canvas ref={canvasRef} role="img" aria-label="Animated Earth globe rendered from NASA Blue Marble satellite imagery" />
    <div className="earth-visual__fallback" aria-hidden="true" />
    <button className="earth-visual__motion" type="button" disabled={reducedMotion} aria-label={reducedMotion ? 'Earth rotation paused by motion preference' : motion ? 'Pause Earth rotation' : 'Start Earth rotation'} aria-pressed={motion && !reducedMotion} onClick={() => setMotion(value => !value)}>{motion && !reducedMotion ? 'Ⅱ' : '▶'}</button>
  </div>;
}
