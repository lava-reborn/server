class lol.gpui.ExitLocationInterface extends lol.gpui.GPUIObject
{
   var close_btn;
   var dispatchEvent;
   var goMap_btn;
   var goOtherLoc_btn;
   var locationInterface;
   function ExitLocationInterface()
   {
      super();
      this.doLater(this,"init");
   }
   function init()
   {
      this.locationInterface = lol.core.SceneShifter.locationScreen;
      this.locationInterface.addEventListener("exitEnabled",this,this.exitEnabled);
      this.goMap_btn.enabled = this.locationInterface.canLeavelocation;
      this.goOtherLoc_btn.enabled = this.locationInterface.canLeavelocation;
      this.goMap_btn._enabled = this.locationInterface.canLeavelocation;
      this.goOtherLoc_btn._enabled = this.locationInterface.canLeavelocation;
      this.goOtherLoc_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitLoc);
      this.goMap_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitGmap);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      if(lol.core.Master.getInstance().currentLocation.isSubLocation)
      {
         this.goMap_btn.enabled = false;
      }
      lol.core.SceneShifter.hotKeyManager.addFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function kill()
   {
      this.goOtherLoc_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitLoc);
      this.goMap_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitGmap);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.locationInterface.removeEventListener("exitEnabled",this,this.exitEnabled);
      lol.core.SceneShifter.hotKeyManager.removeFilter("cancel");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function exitEnabled(obj)
   {
      this.goMap_btn.enabled = obj.value;
      this.goOtherLoc_btn.enabled = obj.value;
      this.goMap_btn._enabled = obj.value;
      this.goOtherLoc_btn._enabled = obj.value;
   }
   function exitLoc()
   {
      this.dispatchEvent({type:"exitLoc",where:"loc"});
   }
   function exitGmap()
   {
      this.dispatchEvent({type:"exitLoc",where:"gmap"});
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
}
