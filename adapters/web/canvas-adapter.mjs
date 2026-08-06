// Example host adapter. It is not part of the language semantics.
export function createCanvasCapabilities(actor, input) {
  return {
    "debug.log": (text) => console.log(text),
    "input.move2d": () => input.direction(),
    "motion.move2d": (delta) => {
      actor.x += Number(delta[0].numerator) / Number(delta[0].denominator);
      actor.y += Number(delta[1].numerator) / Number(delta[1].denominator);
    },
    "animation.play": (name) => {
      actor.animation = name;
    },
  };
}
