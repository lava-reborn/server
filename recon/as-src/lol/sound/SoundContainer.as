class lol.sound.SoundContainer
{
   var __url;
   var _cont;
   var _name;
   var _sound;
   var _type;
   var dispatchEvent;
   var sfx;
   var status = null;
   function SoundContainer(sName)
   {
      lol.events.LEventDispatcher.initialize(this);
      this._name = sName;
   }
   function loadSound(url)
   {
      this.__url = url;
      var _loc3_;
      var _loc2_;
      if(!this.status)
      {
         _loc3_ = new MovieClipLoader();
         _loc2_ = new Object();
         _loc2_.onLoadInit = mx.utils.Delegate.create(this,this.onSoundLoaded);
         _loc2_.onLoadError = mx.utils.Delegate.create(this,this.onLoadError);
         _loc3_.addListener(_loc2_);
         _loc3_.loadClip(url,this._cont);
         this.status = "loading";
      }
      else if(this.status == "loaded")
      {
         this.onSoundLoaded(this._cont);
      }
   }
   function onSoundLoaded(target_mc)
   {
      this.dispatchEvent({type:"onLoad"});
      this.status = "loaded";
   }
   function onLoadError()
   {
      this.status = "failed";
      this.dispatchEvent({type:"failed"});
   }
   function playSound()
   {
   }
   function stop()
   {
      this._sound.stop();
   }
   function get sound()
   {
      return this._sound;
   }
   function get type()
   {
      return this._type;
   }
   function set sound(value)
   {
      this._sound = value;
   }
   function set cont(c)
   {
      this._cont = c;
   }
   function get name()
   {
      return this._name;
   }
   function setVolume(vol)
   {
      this._sound.setVolume(vol);
   }
   function setPan(p)
   {
      this._sound.setPan(p);
   }
   function setFX(fx)
   {
      this.sfx.kill();
      this.sfx = fx;
      this.sfx.sound = this._sound;
      fx.start();
   }
}
