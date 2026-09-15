class lol.sound.SoundManager
{
   var _pathArray;
   var currentSounds;
   var currentTrackName;
   var gameLib;
   var trackLib;
   static var sInstance;
   static var singleCreation;
   static var DEFAULT_TYPE = "default";
   static var TRACK_TYPE = "tracks";
   var muteFlag = true;
   function SoundManager()
   {
      if(lol.sound.SoundManager.singleCreation)
      {
         this.init();
      }
   }
   static function getInstance()
   {
      if(!lol.sound.SoundManager.sInstance)
      {
         lol.sound.SoundManager.singleCreation = true;
         lol.sound.SoundManager.sInstance = new lol.sound.SoundManager();
         lol.sound.SoundManager.singleCreation = false;
      }
      return lol.sound.SoundManager.sInstance;
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.gameLib = lol.sound.SoundTLLibrary.create("game");
      this.trackLib = lol.sound.SoundTrackLibrary.create("tracks");
      this.currentSounds = new Array();
      this.initPathArray();
   }
   function playEventSound(name)
   {
      var _loc4_ = !this._pathArray[name] ? name : this._pathArray[name];
      var _loc5_ = lol.services.SSEmulator.getSoundURL(_loc4_,lol.sound.SoundManager.DEFAULT_TYPE);
      var _loc3_ = this.gameLib.getSound(name);
      _loc3_.loadSound(_loc5_);
      _loc3_.addEventListener("onLoad",this,this.soundLoaded);
   }
   function soundLoaded(obj)
   {
      var _loc1_ = obj.target;
      if(lol.gpui.UserSettings.getSetting("gameSoundVolume") > 0)
      {
         _loc1_.playSound();
      }
   }
   function playSoundTrack(name)
   {
      var _loc3_ = lol.services.SSEmulator.getSoundURL(name,lol.sound.SoundManager.TRACK_TYPE);
      var _loc2_ = this.trackLib.getSound(name);
      _loc2_.loadSound(_loc3_);
      _loc2_.addEventListener("onLoad",this,this.trackLoaded);
   }
   function trackLoaded(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_;
      var _loc3_;
      if(this.currentTrackName != _loc2_.name && lol.gpui.UserSettings.getSetting("musicVolume") > 0)
      {
         this.stopCurrentTrack();
         _loc2_.playSound();
         _loc4_ = lol.gpui.UserSettings.getSetting("musicVolume");
         _loc3_ = new lol.fx.FadeSound(null,0,_loc4_,1000);
         _loc2_.setFX(_loc3_);
         this.currentTrackName = _loc2_.name;
      }
   }
   function stopCurrentTrack()
   {
      var _loc3_ = this.trackLib.getSound(this.currentTrackName);
      var _loc2_ = new lol.fx.FadeSoundStopper(null,1000);
      _loc3_.setFX(_loc2_);
   }
   function musicVolume(vol)
   {
      var _loc2_;
      if(vol > 0)
      {
         this.trackLib.getSound(this.currentTrackName).setVolume(vol);
         if(!this.muteFlag)
         {
            this.muteFlag = true;
            _loc2_ = this.currentTrackName;
            this.currentTrackName = null;
            this.playSoundTrack(_loc2_);
         }
      }
      else
      {
         this.muteFlag = false;
         this.stopCurrentTrack();
      }
   }
   function stopSound(name, type)
   {
      if(type == lol.sound.SoundManager.DEFAULT_TYPE)
      {
         this.gameLib.getSound(name).stop();
      }
      else if(type == lol.sound.SoundManager.TRACK_TYPE)
      {
         this.stopCurrentTrack();
      }
   }
   function initPathArray()
   {
      this._pathArray = new Array();
      this._pathArray[lol.sound.SoundEvent.DAMAGE] = "damage";
      this._pathArray[lol.sound.SoundEvent.DIE] = "die";
      this._pathArray[lol.sound.SoundEvent.FIREARM_FIRE] = "firearm";
      this._pathArray[lol.sound.SoundEvent.ASSAULT_FIRE] = "assault";
      this._pathArray[lol.sound.SoundEvent.MACHINEGUN_FIRE] = "machinegun";
      this._pathArray[lol.sound.SoundEvent.PISTOL_FIRE] = "pistol";
      this._pathArray[lol.sound.SoundEvent.RIFLE_FIRE] = "rifle";
      this._pathArray[lol.sound.SoundEvent.SHOTGUN_FIRE] = "shotgun";
      this._pathArray[lol.sound.SoundEvent.SMG_FIRE] = "smg";
      this._pathArray[lol.sound.SoundEvent.FIREARM_RELOAD] = "reload";
      this._pathArray[lol.sound.SoundEvent.FIST_HIT] = "fist-hit";
      this._pathArray[lol.sound.SoundEvent.FIST_MISS] = "fist-miss";
      this._pathArray[lol.sound.SoundEvent.KNIFE_MISS] = "knife-miss";
      this._pathArray[lol.sound.SoundEvent.KNIFE_OK] = "knife-hit";
   }
}
