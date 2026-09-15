class lol.fx.FadeSoundStopper extends lol.fx.FadeSound
{
   var _sound;
   var calc;
   var maxSteps;
   var startV;
   var stepCount;
   function FadeSoundStopper(sound, t)
   {
      super(sound,sound.getVolume(),0,t);
   }
   function fade()
   {
      super.fade();
      if(this.stepCount >= this.maxSteps)
      {
         this._sound.stop();
      }
   }
   function set sound(s)
   {
      this._sound = s;
      this.startV = s.getVolume();
      this.calc();
   }
   function get sound()
   {
      return this._sound;
   }
}
