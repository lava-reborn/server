class lol.gpui.Introduction extends lol.gpui.GPUIObject
{
   var cont_mc;
   var createEmptyMovieClip;
   var dispatchEvent;
   var locPreloader;
   var mcl;
   var mcl_list;
   var removeEventListener;
   function Introduction()
   {
      super();
      this.init();
   }
   function init()
   {
      this.cont_mc = this.createEmptyMovieClip("cont_mc",0);
      this.mcl = new MovieClipLoader();
      this.mcl_list = new Object();
      this.mcl_list.onLoadProgress = mx.utils.Delegate.create(this,this.onLoadProgress);
      this.mcl_list.onLoadError = mx.utils.Delegate.create(this,this.onLoadError);
      this.mcl_list.onLoadInit = mx.utils.Delegate.create(this,this.onLoadSource);
      this.mcl.addListener(this.mcl_list);
      Stage.addListener(this);
      this.start();
   }
   function start()
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("loadLoc","center");
      this.locPreloader = _loc2_.content;
      this.locPreloader.setTitle("Подождите, идет загрузка.");
      this.skipIntro();
   }
   function onLoadSource(target)
   {
      this.removeEventListener("onLoadProgress",this.locPreloader);
      lol.core.SceneShifter.closeWindow("loadLoc");
      this.onResize();
   }
   function onResize()
   {
      this.cont_mc._x = (Stage.width - this.cont_mc._width) / 2;
      this.cont_mc._y = (Stage.height - this.cont_mc._height) / 2;
   }
   function onLoadProgress(target_mc, bytesLoaded, bytesTotal)
   {
      this.dispatchEvent({type:"onLoadProgress",bytesLoaded:bytesLoaded,bytesTotal:bytesTotal});
   }
   function onLoadError(target_mc, errorCode, httpStatus)
   {
      this.skipIntro();
   }
   function skipIntro()
   {
      lol.core.Master.getInstance().persGen.skipIntro();
   }
}
