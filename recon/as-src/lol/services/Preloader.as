class lol.services.Preloader extends MovieClip
{
   var info_txt;
   var progressBar;
   function Preloader()
   {
      super();
   }
   function onLoadProgress(obj)
   {
      this.showProgress(obj.bytesLoaded,obj.bytesTotal);
   }
   function showProgress(bytesLoaded, bytesTotal)
   {
      var _loc2_ = Math.floor(100 * bytesLoaded / bytesTotal);
      this.progressBar.gotoAndStop(_loc2_);
   }
   function setTitle(title)
   {
      this.info_txt.text = title;
   }
}
