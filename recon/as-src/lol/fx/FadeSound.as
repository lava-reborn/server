class lol.fx.FadeSound
{
   var T;
   var _sound;
   var dV;
   var finishV;
   var interval;
   var maxSteps;
   var startV;
   var stepCount;
   static var fxStore;
   var dt = 40;
   function FadeSound(sound, startVolume, finishVolume, t)
   {
      this._sound = sound;
      this.startV = startVolume;
      this.finishV = finishVolume;
      this.T = t;
      this.calc();
      this.init();
   }
   function init()
   {
      if(!lol.fx.FadeSound.fxStore)
      {
         lol.fx.FadeSound.fxStore = new Array();
      }
      lol.fx.FadeSound.fxStore.push(this);
   }
   function calc()
   {
      this.dV = this.dt * (this.finishV - this.startV) / this.T;
      this.maxSteps = Math.floor(this.T / this.dt) + 1;
   }
   function kill()
   {
      clearInterval(this.interval);
      var _loc2_ = 0;
      while(_loc2_ < lol.fx.FadeSound.fxStore.length)
      {
         if(lol.fx.FadeSound.fxStore[_loc2_] == this)
         {
            lol.fx.FadeSound.fxStore.splice(_loc2_,1);
            return undefined;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function start(n)
   {
      if(this._sound)
      {
         this.stepCount = 0;
         this._sound.setVolume(this.startV);
         this.interval = setInterval(this,"fade",this.dt);
      }
      else
      {
         this.kill();
      }
   }
   function fade()
   {
      var _loc2_ = this._sound.getVolume() + this.dV;
      this._sound.setVolume(_loc2_);
      this.stepCount = this.stepCount + 1;
      if(this.stepCount >= this.maxSteps)
      {
         this._sound.setVolume(this.finishV);
         clearInterval(this.interval);
         this.kill();
      }
   }
   function set sound(s)
   {
      this._sound = s;
   }
   function get sound()
   {
      return this._sound;
   }
}
